# Step Functions + Lambda Pattern
# Tests: Step Functions state machine with Lambda task integrations
# Expected: Step Functions → Lambda connections detected from state machine definition

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
  name = "stepfunctions-execution-role"

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
  name = "stepfunctions-lambda-policy"
  role = aws_iam_role.sfn_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = "*"
      }
    ]
  })
}

# IAM role for Lambda
resource "aws_iam_role" "lambda_role" {
  name = "lambda-execution-role"

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

# Lambda functions
resource "aws_lambda_function" "validate" {
  filename      = "lambda.zip"
  function_name = "order-validator"
  role          = aws_iam_role.lambda_role.arn
  handler       = "index.handler"
  runtime       = "python3.11"
}

resource "aws_lambda_function" "process" {
  filename      = "lambda.zip"
  function_name = "order-processor"
  role          = aws_iam_role.lambda_role.arn
  handler       = "index.handler"
  runtime       = "python3.11"
}

resource "aws_lambda_function" "notify" {
  filename      = "lambda.zip"
  function_name = "order-notifier"
  role          = aws_iam_role.lambda_role.arn
  handler       = "index.handler"
  runtime       = "python3.11"
}

# Step Functions State Machine
resource "aws_sfn_state_machine" "order_workflow" {
  name     = "order-processing-workflow"
  role_arn = aws_iam_role.sfn_role.arn

  definition = jsonencode({
    Comment = "Order processing workflow"
    StartAt = "ValidateOrder"
    States = {
      ValidateOrder = {
        Type     = "Task"
        Resource = aws_lambda_function.validate.arn
        Next     = "ProcessOrder"
      }
      ProcessOrder = {
        Type     = "Task"
        Resource = aws_lambda_function.process.arn
        Next     = "NotifyCustomer"
      }
      NotifyCustomer = {
        Type     = "Task"
        Resource = aws_lambda_function.notify.arn
        End      = true
      }
    }
  })
}
