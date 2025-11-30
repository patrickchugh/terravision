# terraform/main.tf
terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# Variables
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "llm-app"
}

variable "bedrock_model_id" {
  description = "Bedrock model ID"
  type        = string
}

variable "rate_limit_per_hour" {
  description = "Maximum requests per client per hour"
  type        = number
  default     = 100
}

variable "cost_alert_threshold" {
  description = "Cost alert threshold in USD"
  type        = number
  default     = 50
}

# DynamoDB Table for Rate Limiting
resource "aws_dynamodb_table" "api_usage" {
  name         = "${var.project_name}-api-usage"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "client_id"

  attribute {
    name = "client_id"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Name        = "${var.project_name}-api-usage"
    Environment = "production"
  }

  lifecycle {
    prevent_destroy = false
    ignore_changes  = [tags]
  }
}

# IAM Role for Lambda
resource "aws_iam_role" "lambda_role" {
  name = "${var.project_name}-lambda-role"

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

  lifecycle {
    prevent_destroy = false
  }
}

# IAM Policy for Lambda
resource "aws_iam_role_policy" "lambda_policy" {
  name = "${var.project_name}-lambda-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem"
        ]
        Resource = aws_dynamodb_table.api_usage.arn
      }
    ]
  })
}

# Create Lambda deployment package
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/lambda"
  output_path = "${path.module}/lambda_function.zip"
}

# Lambda Function with Response Streaming
resource "aws_lambda_function" "bedrock_proxy" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = "${var.project_name}-bedrock-proxy"
  role             = aws_iam_role.lambda_role.arn
  handler          = "handler.stream_handler"
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  runtime          = "python3.11"
  timeout          = 300
  memory_size      = 512

  environment {
    variables = {
      BEDROCK_MODEL_ID    = var.bedrock_model_id
      DYNAMODB_TABLE      = aws_dynamodb_table.api_usage.name
      RATE_LIMIT_PER_HOUR = var.rate_limit_per_hour
    }
  }

  tags = {
    Name = "${var.project_name}-bedrock-proxy"
  }
}

# Lambda Function URL for Streaming
resource "aws_lambda_function_url" "bedrock_proxy_url" {
  function_name      = aws_lambda_function.bedrock_proxy.function_name
  authorization_type = "NONE"
  invoke_mode        = "RESPONSE_STREAM"

  cors {
    allow_origins = ["*"]
    allow_methods = ["POST"]
    allow_headers = ["content-type"]
    max_age       = 86400
  }
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${aws_lambda_function.bedrock_proxy.function_name}"
  retention_in_days = 7

  tags = {
    Name = "${var.project_name}-lambda-logs"
  }
}

# HTTP API Gateway v2 (supports streaming)
resource "aws_apigatewayv2_api" "http_api" {
  name          = "${var.project_name}-http-api"
  protocol_type = "HTTP"
  description   = "HTTP API for streaming Lambda responses"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["POST", "OPTIONS"]
    allow_headers = ["content-type"]
    max_age       = 86400
  }
}

# HTTP API Integration with Lambda
resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.http_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.bedrock_proxy.invoke_arn
  payload_format_version = "2.0"
  timeout_milliseconds   = 30000
}

# HTTP API Route
resource "aws_apigatewayv2_route" "chat" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "POST /chat"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

# HTTP API Stage
resource "aws_apigatewayv2_stage" "prod" {
  api_id      = aws_apigatewayv2_api.http_api.id
  name        = "prod"
  auto_deploy = true

  default_route_settings {
    throttling_burst_limit = 50
    throttling_rate_limit  = 100
  }
}

# Lambda Permission for HTTP API
resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowHTTPAPIInvoke"
  action        = "lambda:InvokeFunctionUrl"
  function_name = aws_lambda_function.bedrock_proxy.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http_api.execution_arn}/*/*"
}

# CloudWatch Alarm for Costs
resource "aws_cloudwatch_metric_alarm" "cost_alert" {
  alarm_name          = "${var.project_name}-cost-alert"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "EstimatedCharges"
  namespace           = "AWS/Billing"
  period              = 3600
  statistic           = "Maximum"
  threshold           = var.cost_alert_threshold
  alarm_description   = "Alert when estimated charges exceed threshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    Currency = "USD"
  }
}

# CloudWatch Alarm for Lambda Errors
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "${var.project_name}-lambda-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = "Alert when Lambda errors exceed threshold"

  dimensions = {
    FunctionName = aws_lambda_function.bedrock_proxy.function_name
  }
}

# Outputs
output "api_endpoint" {
  description = "HTTP API Gateway endpoint URL"
  value       = "${aws_apigatewayv2_stage.prod.invoke_url}/chat"
}

output "function_url" {
  description = "Lambda Function URL (direct streaming)"
  value       = aws_lambda_function_url.bedrock_proxy_url.function_url
}

output "api_id" {
  description = "HTTP API Gateway ID"
  value       = aws_apigatewayv2_api.http_api.id
}

output "lambda_function_name" {
  description = "Lambda function name"
  value       = aws_lambda_function.bedrock_proxy.function_name
}

output "dynamodb_table_name" {
  description = "DynamoDB table name"
  value       = aws_dynamodb_table.api_usage.name
}
