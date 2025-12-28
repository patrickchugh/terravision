# DynamoDB Streams + Lambda Test Fixture
# Purpose: Test Lambda event source mapping visualization
# Expected: DynamoDB table → Lambda function connection via streams

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

# DynamoDB table with stream enabled
resource "aws_dynamodb_table" "orders" {
  name           = "orders-table"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "OrderId"
  stream_enabled = true
  stream_view_type = "NEW_AND_OLD_IMAGES"

  attribute {
    name = "OrderId"
    type = "S"
  }

  tags = {
    Name        = "orders-table"
    Environment = "test"
  }
}

# Lambda function that processes stream events
resource "aws_lambda_function" "stream_processor" {
  filename      = "lambda.zip"
  function_name = "dynamodb-stream-processor"
  role          = aws_iam_role.lambda_role.arn
  handler       = "index.handler"
  runtime       = "nodejs18.x"

  environment {
    variables = {
      TABLE_NAME = aws_dynamodb_table.orders.name
    }
  }
}

# IAM role for Lambda
resource "aws_iam_role" "lambda_role" {
  name = "lambda-stream-processor-role"

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

# IAM policy for Lambda to read DynamoDB stream
resource "aws_iam_role_policy" "lambda_dynamodb_policy" {
  name = "lambda-dynamodb-stream-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "dynamodb:DescribeStream",
        "dynamodb:GetRecords",
        "dynamodb:GetShardIterator",
        "dynamodb:ListStreams"
      ]
      Resource = "${aws_dynamodb_table.orders.arn}/stream/*"
    }]
  })
}

# Lambda event source mapping to DynamoDB stream
resource "aws_lambda_event_source_mapping" "dynamodb_stream" {
  event_source_arn  = aws_dynamodb_table.orders.stream_arn
  function_name     = aws_lambda_function.stream_processor.arn
  starting_position = "LATEST"
  batch_size        = 100
}

# Second DynamoDB table for user events
resource "aws_dynamodb_table" "users" {
  name           = "users-table"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "UserId"
  stream_enabled = true
  stream_view_type = "NEW_IMAGE"

  attribute {
    name = "UserId"
    type = "S"
  }
}

# Second Lambda for user events
resource "aws_lambda_function" "user_event_processor" {
  filename      = "lambda.zip"
  function_name = "user-event-processor"
  role          = aws_iam_role.lambda_role.arn
  handler       = "index.handler"
  runtime       = "nodejs18.x"
}

# Event source mapping for user table
resource "aws_lambda_event_source_mapping" "user_stream" {
  event_source_arn  = aws_dynamodb_table.users.stream_arn
  function_name     = aws_lambda_function.user_event_processor.arn
  starting_position = "LATEST"
}

# Kinesis stream for additional testing
resource "aws_kinesis_stream" "events" {
  name             = "application-events"
  shard_count      = 1
  retention_period = 24
}

# Lambda for Kinesis stream processing
resource "aws_lambda_function" "kinesis_processor" {
  filename      = "lambda.zip"
  function_name = "kinesis-processor"
  role          = aws_iam_role.lambda_role.arn
  handler       = "index.handler"
  runtime       = "nodejs18.x"
}

# Event source mapping for Kinesis
resource "aws_lambda_event_source_mapping" "kinesis_stream" {
  event_source_arn  = aws_kinesis_stream.events.arn
  function_name     = aws_lambda_function.kinesis_processor.arn
  starting_position = "LATEST"
}

# IAM policy for Kinesis
resource "aws_iam_role_policy" "lambda_kinesis_policy" {
  name = "lambda-kinesis-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "kinesis:DescribeStream",
        "kinesis:GetRecords",
        "kinesis:GetShardIterator",
        "kinesis:ListStreams"
      ]
      Resource = aws_kinesis_stream.events.arn
    }]
  })
}
