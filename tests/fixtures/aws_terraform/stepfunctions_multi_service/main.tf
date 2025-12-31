# Step Functions Multi-Service Pattern
# Tests: Step Functions state machine with Lambda, DynamoDB, SNS integrations
# Expected: Step Functions → Lambda, DynamoDB, SNS connections detected from state machine definition

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

# IAM role for Step Functions
resource "aws_iam_role" "sfn_role" {
  name = "stepfunctions-multiservice-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "states.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "sfn_policy" {
  name = "stepfunctions-multiservice-policy"
  role = aws_iam_role.sfn_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction",
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "sns:Publish"
        ]
        Resource = "*"
      }
    ]
  })
}

# IAM role for Lambda
resource "aws_iam_role" "lambda_role" {
  name = "lambda-multiservice-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# Lambda function
resource "aws_lambda_function" "transform" {
  filename      = "lambda.zip"
  function_name = "data-transformer"
  role          = aws_iam_role.lambda_role.arn
  handler       = "index.handler"
  runtime       = "python3.11"
}

# DynamoDB table
resource "aws_dynamodb_table" "orders" {
  name           = "orders-table"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "orderId"

  attribute {
    name = "orderId"
    type = "S"
  }
}

# SNS topic
resource "aws_sns_topic" "notifications" {
  name = "order-notifications"
}

# Step Functions State Machine with multi-service integrations
resource "aws_sfn_state_machine" "data_pipeline" {
  name     = "data-processing-pipeline"
  role_arn = aws_iam_role.sfn_role.arn

  definition = jsonencode({
    Comment = "Data processing pipeline with multiple AWS services"
    StartAt = "TransformData"
    States = {
      TransformData = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = aws_lambda_function.transform.arn
          "Payload.$"  = "$"
        }
        Next = "SaveToDynamoDB"
      }
      SaveToDynamoDB = {
        Type     = "Task"
        Resource = "arn:aws:states:::dynamodb:putItem"
        Parameters = {
          TableName = aws_dynamodb_table.orders.name
          Item = {
            "orderId" = {
              "S.$" = "$.orderId"
            }
            "data" = {
              "S.$" = "$.data"
            }
          }
        }
        Next = "PublishNotification"
      }
      PublishNotification = {
        Type     = "Task"
        Resource = "arn:aws:states:::sns:publish"
        Parameters = {
          TopicArn = aws_sns_topic.notifications.arn
          "Message.$" = "$.message"
        }
        End = true
      }
    }
  })
}
