# lambda/handler.py
import json
import boto3
import hashlib
import os
from datetime import datetime
from decimal import Decimal

bedrock = boto3.client('bedrock-runtime')
dynamodb = boto3.resource('dynamodb')

# Get environment variables
TABLE_NAME = os.environ['DYNAMODB_TABLE']
MODEL_ID = os.environ['BEDROCK_MODEL_ID']
RATE_LIMIT = int(os.environ['RATE_LIMIT_PER_HOUR'])

table = dynamodb.Table(TABLE_NAME)

def get_client_id(event):
    """Generate identifier from IP + User-Agent"""
    ip = event['requestContext']['identity']['sourceIp']
    user_agent = event['headers'].get('User-Agent', '')
    return hashlib.sha256(f"{ip}:{user_agent}".encode()).hexdigest()[:16]

def check_rate_limit(client_id):
    """Check if client has exceeded rate limits"""
    try:
        response = table.get_item(Key={'client_id': client_id})
        
        if 'Item' in response:
            item = response['Item']
            if item['request_count'] >= RATE_LIMIT:
                time_diff = datetime.now().timestamp() - float(item['window_start'])
                if time_diff < 3600:  # 1 hour
                    return False, item['request_count']
            
        return True, 0
    except Exception as e:
        print(f"Rate limit check error: {e}")
        return True, 0

def update_usage(client_id):
    """Update usage counters"""
    now = datetime.now().timestamp()
    
    try:
        table.update_item(
            Key={'client_id': client_id},
            UpdateExpression='''
                SET request_count = if_not_exists(request_count, :zero) + :inc,
                    window_start = if_not_exists(window_start, :now),
                    last_request = :now,
                    ttl = :ttl
            ''',
            ExpressionAttributeValues={
                ':inc': 1,
                ':zero': 0,
                ':now': Decimal(str(now)),
                ':ttl': int(now) + 86400
            }
        )
    except Exception as e:
        print(f"Usage update error: {e}")

def proxy_bedrock(event, context):
    """Main Lambda handler"""
    
    # Get client identifier
    client_id = get_client_id(event)
    
    # Check rate limit
    allowed, current_count = check_rate_limit(client_id)
    if not allowed:
        return {
            'statusCode': 429,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Rate limit exceeded',
                'message': f'Maximum {RATE_LIMIT} requests per hour. Please try again later.',
                'requests_made': current_count
            })
        }
    
    try:
        # Parse request
        body = json.loads(event['body'])
        
        # Build Bedrock request
        bedrock_request = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": body.get('max_tokens', 512),
            "messages": body['messages']
        }
        
        # Call Bedrock
        response = bedrock.invoke_model(
            modelId=MODEL_ID,
            body=json.dumps(bedrock_request)
        )
        
        # Parse response
        response_body = json.loads(response['body'].read())
        
        # Update usage tracking
        update_usage(client_id)
        
        # Log for analytics
        print(json.dumps({
            'client_id': client_id,
            'timestamp': datetime.now().isoformat(),
            'message_count': len(body['messages']),
            'input_tokens': response_body.get('usage', {}).get('input_tokens'),
            'output_tokens': response_body.get('usage', {}).get('output_tokens')
        }))
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response_body)
        }
        
    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Invalid JSON'})
        }
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Internal server error'})
        }