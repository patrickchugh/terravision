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
          "bedrock:InvokeModel"
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

# Lambda Function
resource "aws_lambda_function" "bedrock_proxy" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = "${var.project_name}-bedrock-proxy"
  role             = aws_iam_role.lambda_role.arn
  handler          = "handler.proxy_bedrock"
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  runtime          = "python3.11"
  timeout          = 60
  memory_size      = 256

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

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${aws_lambda_function.bedrock_proxy.function_name}"
  retention_in_days = 7

  tags = {
    Name = "${var.project_name}-lambda-logs"
  }
}

# API Gateway REST API
resource "aws_api_gateway_rest_api" "api" {
  name        = "${var.project_name}-api"
  description = "LLM App API Gateway"

  endpoint_configuration {
    types = ["REGIONAL"]
  }
}

# API Gateway Resource
resource "aws_api_gateway_resource" "chat" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_rest_api.api.root_resource_id
  path_part   = "chat"
}

# API Gateway Method
resource "aws_api_gateway_method" "post_chat" {
  rest_api_id   = aws_api_gateway_rest_api.api.id
  resource_id   = aws_api_gateway_resource.chat.id
  http_method   = "POST"
  authorization = "NONE"

  request_validator_id = aws_api_gateway_request_validator.validator.id

  request_models = {
    "application/json" = aws_api_gateway_model.request_model.name
  }
}

# Request Validator
resource "aws_api_gateway_request_validator" "validator" {
  name                        = "${var.project_name}-validator"
  rest_api_id                 = aws_api_gateway_rest_api.api.id
  validate_request_body       = true
  validate_request_parameters = false
}

# API Gateway Model for JSON Schema Validation
resource "aws_api_gateway_model" "request_model" {
  rest_api_id  = aws_api_gateway_rest_api.api.id
  name         = "ChatRequest"
  description  = "JSON schema for chat requests"
  content_type = "application/json"

  schema = jsonencode({
    "$schema" = "http://json-schema.org/draft-04/schema#"
    title     = "ChatRequest"
    type      = "object"
    required  = ["messages"]
    properties = {
      messages = {
        type     = "array"
        maxItems = 10
        items = {
          type     = "object"
          required = ["role", "content"]
          properties = {
            role = {
              type = "string"
              enum = ["user", "assistant"]
            }
            content = {
              type      = "string"
              maxLength = 4000
            }
          }
        }
      }
      max_tokens = {
        type    = "integer"
        minimum = 1
        maximum = 1024
      }
    }
    additionalProperties = false
  })
}

# API Gateway Integration
resource "aws_api_gateway_integration" "lambda_integration" {
  rest_api_id             = aws_api_gateway_rest_api.api.id
  resource_id             = aws_api_gateway_resource.chat.id
  http_method             = aws_api_gateway_method.post_chat.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.bedrock_proxy.invoke_arn
}

# CORS - OPTIONS Method
resource "aws_api_gateway_method" "options_chat" {
  rest_api_id   = aws_api_gateway_rest_api.api.id
  resource_id   = aws_api_gateway_resource.chat.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_integration" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  resource_id = aws_api_gateway_resource.chat.id
  http_method = aws_api_gateway_method.options_chat.http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "options_response" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  resource_id = aws_api_gateway_resource.chat.id
  http_method = aws_api_gateway_method.options_chat.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_integration_response" "options_integration_response" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  resource_id = aws_api_gateway_resource.chat.id
  http_method = aws_api_gateway_method.options_chat.http_method
  status_code = aws_api_gateway_method_response.options_response.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'POST,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }

  depends_on = [aws_api_gateway_integration.options_integration]
}

# API Gateway Deployment
resource "aws_api_gateway_deployment" "deployment" {
  rest_api_id = aws_api_gateway_rest_api.api.id

  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.chat.id,
      aws_api_gateway_method.post_chat.id,
      aws_api_gateway_integration.lambda_integration.id,
      aws_api_gateway_method.options_chat.id,
      aws_api_gateway_integration.options_integration.id,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [
    aws_api_gateway_integration.lambda_integration,
    aws_api_gateway_integration.options_integration
  ]
}

# API Gateway Stage
resource "aws_api_gateway_stage" "prod" {
  deployment_id = aws_api_gateway_deployment.deployment.id
  rest_api_id   = aws_api_gateway_rest_api.api.id
  stage_name    = "prod"

  tags = {
    Name = "${var.project_name}-prod"
  }
}

# API Gateway Method Settings for Throttling
resource "aws_api_gateway_method_settings" "all" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  stage_name  = aws_api_gateway_stage.prod.stage_name
  method_path = "*/*"

  settings {
    throttling_burst_limit = 50
    throttling_rate_limit  = 100
  }
}

# Lambda Permission for API Gateway
resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.bedrock_proxy.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.api.execution_arn}/*/*"
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
  description = "API Gateway endpoint URL"
  value       = "${aws_api_gateway_stage.prod.invoke_url}/chat"
}

output "api_id" {
  description = "API Gateway ID"
  value       = aws_api_gateway_rest_api.api.id
}

output "lambda_function_name" {
  description = "Lambda function name"
  value       = aws_lambda_function.bedrock_proxy.function_name
}

output "dynamodb_table_name" {
  description = "DynamoDB table name"
  value       = aws_dynamodb_table.api_usage.name
}
