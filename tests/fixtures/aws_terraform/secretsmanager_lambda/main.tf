# Secrets Manager + Lambda Pattern
# Tests: Lambda function accessing database credentials from Secrets Manager
# Expected: Lambda → Secrets Manager connection detected from environment variable reference

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

# Database credentials secret
resource "aws_secretsmanager_secret" "db_credentials" {
  name        = "database-credentials"
  description = "RDS database credentials"
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    username = "admin"
    password = "changeme"
    engine   = "postgres"
    host     = "db.example.com"
    port     = 5432
  })
}

# IAM role for Lambda
resource "aws_iam_role" "lambda_role" {
  name = "lambda-secretsmanager-role"

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

# Policy to access secrets
resource "aws_iam_role_policy" "lambda_secrets_policy" {
  name = "lambda-secrets-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ]
      Resource = aws_secretsmanager_secret.db_credentials.arn
    }]
  })
}

# Lambda function that uses the secret
resource "aws_lambda_function" "app" {
  filename      = "lambda.zip"
  function_name = "database-app"
  role          = aws_iam_role.lambda_role.arn
  handler       = "index.handler"
  runtime       = "python3.11"

  environment {
    variables = {
      DB_SECRET_ARN = aws_secretsmanager_secret.db_credentials.arn
    }
  }
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${aws_lambda_function.app.function_name}"
  retention_in_days = 7
}
