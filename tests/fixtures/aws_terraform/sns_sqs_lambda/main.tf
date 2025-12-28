# SNS + SQS + Lambda Fan-Out Test Fixture
# Purpose: Test event-driven fan-out architecture visualization
# Expected: SNS topic → SQS queues + Lambda subscribers

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

# SNS topic for order events
resource "aws_sns_topic" "order_events" {
  name = "order-events"
}

# SQS queue for order processing
resource "aws_sqs_queue" "order_processing" {
  name                      = "order-processing-queue"
  delay_seconds             = 0
  max_message_size          = 262144
  message_retention_seconds = 345600
  receive_wait_time_seconds = 10
}

# SQS queue for notifications
resource "aws_sqs_queue" "notifications" {
  name = "notification-queue"
}

# SNS subscription to first SQS queue
resource "aws_sns_topic_subscription" "order_processing_subscription" {
  topic_arn = aws_sns_topic.order_events.arn
  protocol  = "sqs"
  endpoint  = aws_sqs_queue.order_processing.arn
}

# SNS subscription to second SQS queue
resource "aws_sns_topic_subscription" "notifications_subscription" {
  topic_arn = aws_sns_topic.order_events.arn
  protocol  = "sqs"
  endpoint  = aws_sqs_queue.notifications.arn
}

# Lambda function for email notifications
resource "aws_lambda_function" "email_notifier" {
  filename      = "lambda.zip"
  function_name = "email-notifier"
  role          = aws_iam_role.lambda_role.arn
  handler       = "index.handler"
  runtime       = "nodejs18.x"

  environment {
    variables = {
      EMAIL_FROM = "noreply@example.com"
    }
  }
}

# SNS subscription directly to Lambda
resource "aws_sns_topic_subscription" "lambda_subscription" {
  topic_arn = aws_sns_topic.order_events.arn
  protocol  = "lambda"
  endpoint  = aws_lambda_function.email_notifier.arn
}

# IAM role for Lambda
resource "aws_iam_role" "lambda_role" {
  name = "lambda-sns-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

# Permission for SNS to invoke Lambda
resource "aws_lambda_permission" "allow_sns" {
  statement_id  = "AllowExecutionFromSNS"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.email_notifier.function_name
  principal     = "sns.amazonaws.com"
  source_arn    = aws_sns_topic.order_events.arn
}

# Lambda function that processes from SQS
resource "aws_lambda_function" "order_processor" {
  filename      = "lambda.zip"
  function_name = "order-processor"
  role          = aws_iam_role.lambda_role.arn
  handler       = "index.handler"
  runtime       = "nodejs18.x"
}

# Lambda event source mapping from SQS
resource "aws_lambda_event_source_mapping" "sqs_to_lambda" {
  event_source_arn = aws_sqs_queue.order_processing.arn
  function_name    = aws_lambda_function.order_processor.arn
  batch_size       = 10
}

# SQS queue policy to allow SNS to send messages
resource "aws_sqs_queue_policy" "order_processing_policy" {
  queue_url = aws_sqs_queue.order_processing.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = "*"
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.order_processing.arn
      Condition = {
        ArnEquals = {
          "aws:SourceArn" = aws_sns_topic.order_events.arn
        }
      }
    }]
  })
}

resource "aws_sqs_queue_policy" "notifications_policy" {
  queue_url = aws_sqs_queue.notifications.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = "*"
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.notifications.arn
      Condition = {
        ArnEquals = {
          "aws:SourceArn" = aws_sns_topic.order_events.arn
        }
      }
    }]
  })
}
