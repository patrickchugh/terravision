import json
import os
import boto3
from datetime import datetime, timedelta

bedrock = boto3.client('bedrock-runtime', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['DYNAMODB_TABLE'])

def check_rate_limit(client_id):
    """Check if client has exceeded rate limit"""
    try:
        response = table.get_item(Key={'client_id': client_id})
        if 'Item' in response:
            count = response['Item'].get('count', 0)
            if count >= int(os.environ['RATE_LIMIT_PER_HOUR']):
                return False
        return True
    except Exception:
        return True

def increment_usage(client_id):
    """Increment usage counter"""
    ttl = int((datetime.now() + timedelta(hours=1)).timestamp())
    table.update_item(
        Key={'client_id': client_id},
        UpdateExpression='ADD #count :inc SET #ttl = :ttl',
        ExpressionAttributeNames={'#count': 'count', '#ttl': 'ttl'},
        ExpressionAttributeValues={':inc': 1, ':ttl': ttl}
    )

def stream_handler(event, context):
    """Lambda handler with response streaming"""
    # Get client ID from request
    client_id = event.get('requestContext', {}).get('http', {}).get('sourceIp', 'unknown')
    
    # Check rate limit
    if not check_rate_limit(client_id):
        return {
            'statusCode': 429,
            'body': json.dumps({'error': 'Rate limit exceeded'})
        }
    
    # Parse request body
    try:
        body = json.loads(event.get('body', '{}'))
        messages = body.get('messages', [])
        max_tokens = body.get('max_tokens', 1024)
    except Exception as e:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': f'Invalid request: {str(e)}'})
        }
    
    # Increment usage
    increment_usage(client_id)
    
    # Prepare Bedrock request
    bedrock_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": messages
    }
    
    # Stream response from Bedrock
    try:
        response = bedrock.invoke_model_with_response_stream(
            modelId=os.environ['BEDROCK_MODEL_ID'],
            body=json.dumps(bedrock_body)
        )
        
        # Get response stream from Lambda context
        response_stream = awslambdaric.lambda_context.ResponseStream(context)
        
        # Stream chunks
        for event in response['body']:
            if 'chunk' in event:
                chunk_data = json.loads(event['chunk']['bytes'])
                if chunk_data['type'] == 'content_block_delta':
                    text = chunk_data['delta'].get('text', '')
                    if text:
                        response_stream.write(text.encode('utf-8'))
        
        response_stream.end()
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'Bedrock error: {str(e)}'})
        }

# Import after function definition to avoid circular import
try:
    import awslambdaric.lambda_context
except ImportError:
    pass
