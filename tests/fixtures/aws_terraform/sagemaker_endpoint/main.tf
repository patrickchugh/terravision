# SageMaker Endpoint + Model Pattern
# Tests: SageMaker endpoint, model, configuration consolidation
# Expected: Consolidated SageMaker endpoint with S3 model artifacts connection

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

# S3 bucket for model artifacts
resource "aws_s3_bucket" "model_artifacts" {
  bucket = "ml-model-artifacts"
}

# IAM role for SageMaker
resource "aws_iam_role" "sagemaker_role" {
  name = "sagemaker-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "sagemaker.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "sagemaker_full_access" {
  role       = aws_iam_role.sagemaker_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSageMakerFullAccess"
}

# SageMaker Model
resource "aws_sagemaker_model" "xgboost_model" {
  name               = "xgboost-model"
  execution_role_arn = aws_iam_role.sagemaker_role.arn

  primary_container {
    image          = "433757028032.dkr.ecr.us-east-1.amazonaws.com/xgboost:latest"
    model_data_url = "s3://${aws_s3_bucket.model_artifacts.bucket}/model.tar.gz"
  }
}

# SageMaker Endpoint Configuration
resource "aws_sagemaker_endpoint_configuration" "xgboost_config" {
  name = "xgboost-endpoint-config"

  production_variants {
    variant_name           = "primary"
    model_name             = aws_sagemaker_model.xgboost_model.name
    initial_instance_count = 1
    instance_type          = "ml.m5.large"
  }
}

# SageMaker Endpoint
resource "aws_sagemaker_endpoint" "xgboost_endpoint" {
  name                 = "xgboost-endpoint"
  endpoint_config_name = aws_sagemaker_endpoint_configuration.xgboost_config.name
}

# Lambda function that invokes the SageMaker endpoint
resource "aws_lambda_function" "predictor" {
  filename      = "lambda.zip"
  function_name = "ml-predictor"
  role          = aws_iam_role.lambda_role.arn
  handler       = "index.handler"
  runtime       = "python3.11"

  environment {
    variables = {
      SAGEMAKER_ENDPOINT = aws_sagemaker_endpoint.xgboost_endpoint.name
    }
  }
}

resource "aws_iam_role" "lambda_role" {
  name = "lambda-sagemaker-role"

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

resource "aws_iam_role_policy" "lambda_sagemaker_policy" {
  name = "lambda-sagemaker-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sagemaker:InvokeEndpoint"
        ]
        Resource = aws_sagemaker_endpoint.xgboost_endpoint.arn
      }
    ]
  })
}
