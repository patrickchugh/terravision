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
  handler          = "index.handler"
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  runtime          = "nodejs20.x"
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
    allow_methods = ["*"]
    allow_headers = ["*"]
    max_age       = 86400
  }
}

# Lambda Permission for Function URL
resource "aws_lambda_permission" "function_url" {
  statement_id           = "AllowFunctionURLInvoke"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.bedrock_proxy.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${aws_lambda_function.bedrock_proxy.function_name}"
  retention_in_days = 7

  tags = {
    Name = "${var.project_name}-lambda-logs"
  }
}

# REST API Gateway with streaming support
resource "aws_api_gateway_rest_api" "api" {
  name        = "${var.project_name}-rest-api"
  description = "REST API with Lambda streaming"
}

resource "aws_api_gateway_resource" "chat" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_rest_api.api.root_resource_id
  path_part   = "chat"
}

resource "aws_api_gateway_method" "post_chat" {
  rest_api_id   = aws_api_gateway_rest_api.api.id
  resource_id   = aws_api_gateway_resource.chat.id
  http_method   = "POST"
  authorization = "NONE"
}

# Create integration with streaming using AWS CLI
resource "null_resource" "lambda_integration" {
  triggers = {
    method_id  = aws_api_gateway_method.post_chat.id
    lambda_arn = aws_lambda_function.bedrock_proxy.arn
  }

  provisioner "local-exec" {
    command = <<-EOT
      aws apigateway put-integration \
        --rest-api-id ${aws_api_gateway_rest_api.api.id} \
        --resource-id ${aws_api_gateway_resource.chat.id} \
        --http-method POST \
        --type AWS_PROXY \
        --integration-http-method POST \
        --uri "arn:aws:apigateway:${var.aws_region}:lambda:path/2021-11-15/functions/${aws_lambda_function.bedrock_proxy.arn}/response-streaming-invocations" \
        --timeout-in-millis 300000 \
        --response-transfer-mode STREAM \
        --region ${var.aws_region}
    EOT
  }

  provisioner "local-exec" {
    when    = destroy
    command = "echo 'Integration will be deleted with API Gateway resource'"
  }

  depends_on = [aws_api_gateway_method.post_chat]
}

resource "aws_api_gateway_deployment" "deployment" {
  rest_api_id = aws_api_gateway_rest_api.api.id

  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.chat.id,
      aws_api_gateway_method.post_chat.id,
      null_resource.lambda_integration.id,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [null_resource.lambda_integration]
}

resource "aws_api_gateway_stage" "prod" {
  deployment_id = aws_api_gateway_deployment.deployment.id
  rest_api_id   = aws_api_gateway_rest_api.api.id
  stage_name    = "prod"
}

resource "aws_api_gateway_method_settings" "streaming" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  stage_name  = aws_api_gateway_stage.prod.stage_name
  method_path = "chat/POST"

  settings {
    throttling_burst_limit = 50
    throttling_rate_limit  = 100
  }
}



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
  description = "REST API Gateway endpoint URL"
  value       = "${aws_api_gateway_stage.prod.invoke_url}/chat"
}

output "function_url" {
  description = "Lambda Function URL (direct streaming)"
  value       = aws_lambda_function_url.bedrock_proxy_url.function_url
}

output "api_id" {
  description = "REST API Gateway ID"
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
