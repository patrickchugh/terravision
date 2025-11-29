# lambda/handler.py
import json
import os
import hashlib
from datetime import datetime
from decimal import Decimal

# Lazy import to catch errors
try:
    import boto3  # type: ignore

    bedrock = boto3.client("bedrock-runtime")
    dynamodb = boto3.resource("dynamodb")
except Exception as e:
    print(f"Failed to initialize AWS clients: {e}")
    bedrock = None
    dynamodb = None

# Get environment variables
TABLE_NAME = os.environ.get("DYNAMODB_TABLE", "")
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "")
RATE_LIMIT = int(os.environ.get("RATE_LIMIT_PER_HOUR", 100))


def get_client_id(event):
    """Generate identifier from IP + User-Agent"""
    try:
        ip = (
            event.get("requestContext", {})
            .get("identity", {})
            .get("sourceIp", "unknown")
        )
        user_agent = event.get("headers", {}).get("User-Agent", "")
        return hashlib.sha256(f"{ip}:{user_agent}".encode()).hexdigest()[:16]
    except Exception as e:
        print(f"Error getting client ID: {e}")
        return "default"


def check_rate_limit(client_id):
    """Check if client has exceeded rate limits"""
    if not dynamodb:
        return True, 0

    try:
        table = dynamodb.Table(TABLE_NAME)
        response = table.get_item(Key={"client_id": client_id})

        if "Item" in response:
            item = response["Item"]
            if item.get("request_count", 0) >= RATE_LIMIT:
                time_diff = datetime.now().timestamp() - float(
                    item.get("window_start", 0)
                )
                if time_diff < 3600:
                    return False, item["request_count"]

        return True, 0
    except Exception as e:
        print(f"Rate limit check error: {e}")
        return True, 0


def update_usage(client_id):
    """Update usage counters"""
    if not dynamodb:
        return

    now = datetime.now().timestamp()

    try:
        table = dynamodb.Table(TABLE_NAME)
        table.update_item(
            Key={"client_id": client_id},
            UpdateExpression="""
                SET request_count = if_not_exists(request_count, :zero) + :inc,
                    window_start = if_not_exists(window_start, :now),
                    last_request = :now,
                    #ttl = :ttl
            """,
            ExpressionAttributeNames={
                "#ttl": "ttl"
            },
            ExpressionAttributeValues={
                ":inc": 1,
                ":zero": 0,
                ":now": Decimal(str(now)),
                ":ttl": int(now) + 86400,
            },
        )
    except Exception as e:
        print(f"Usage update error: {e}")


def proxy_bedrock(event, context):
    """Main Lambda handler"""

    print(f"Event: {json.dumps(event)}")

    # Validate environment
    if not bedrock:
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps(
                {
                    "error": "Service initialization failed",
                    "message": "AWS SDK not properly initialized",
                }
            ),
        }

    if not MODEL_ID:
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps(
                {"error": "Configuration error", "message": "MODEL_ID not set"}
            ),
        }

    # Get client identifier
    client_id = get_client_id(event)
    print(f"Client ID: {client_id}")

    # Check rate limit
    allowed, current_count = check_rate_limit(client_id)
    if not allowed:
        return {
            "statusCode": 429,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps(
                {
                    "error": "Rate limit exceeded",
                    "message": f"Maximum {RATE_LIMIT} requests per hour. Please try again later.",
                    "requests_made": current_count,
                }
            ),
        }

    try:
        # Parse request body
        if not event.get("body"):
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                },
                "body": json.dumps({"error": "Missing request body"}),
            }

        body = json.loads(event["body"])
        print(f"Parsed body: {json.dumps(body)}")

        # Validate required fields
        if "messages" not in body:
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                },
                "body": json.dumps({"error": "Missing required field: messages"}),
            }

        # Build Bedrock request
        bedrock_request = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": body.get("max_tokens", 512),
            "messages": body["messages"],
        }

        print(f"Calling Bedrock with model: {MODEL_ID}")
        print(f"Request: {json.dumps(bedrock_request)}")

        # Call Bedrock
        response = bedrock.invoke_model(
            modelId=MODEL_ID, body=json.dumps(bedrock_request)
        )

        print("Bedrock call successful")

        # Parse response
        response_body = json.loads(response["body"].read())
        print(f"Response received: {json.dumps(response_body)}")

        # Update usage tracking
        update_usage(client_id)

        # Log for analytics
        print(
            json.dumps(
                {
                    "event": "api_call",
                    "client_id": client_id,
                    "timestamp": datetime.now().isoformat(),
                    "message_count": len(body["messages"]),
                    "input_tokens": response_body.get("usage", {}).get("input_tokens"),
                    "output_tokens": response_body.get("usage", {}).get(
                        "output_tokens"
                    ),
                }
            )
        )

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps(response_body),
        }

    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        return {
            "statusCode": 400,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps({"error": "Invalid JSON", "details": str(e)}),
        }
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        import traceback

        traceback.print_exc()
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps({"error": "Internal server error", "message": str(e)}),
        }
