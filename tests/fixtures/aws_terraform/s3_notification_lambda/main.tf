# S3 Bucket Notification to Lambda Pattern
# Tests: S3 bucket event notifications triggering Lambda functions
# Expected: S3 → Lambda connection detected from notification configuration

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

# S3 bucket
resource "aws_s3_bucket" "uploads" {
  bucket = "image-uploads-bucket"
}

# IAM role for Lambda
resource "aws_iam_role" "lambda_role" {
  name = "s3-event-processor-role"

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

# Lambda function to process S3 events
resource "aws_lambda_function" "image_processor" {
  filename      = "lambda.zip"
  function_name = "image-processor"
  role          = aws_iam_role.lambda_role.arn
  handler       = "index.handler"
  runtime       = "python3.11"

  environment {
    variables = {
      DESTINATION_BUCKET = "processed-images"
    }
  }
}

# Lambda permission for S3 to invoke
resource "aws_lambda_permission" "allow_s3" {
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.image_processor.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.uploads.arn
}

# S3 bucket notification configuration
resource "aws_s3_bucket_notification" "upload_notification" {
  bucket = aws_s3_bucket.uploads.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.image_processor.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "uploads/"
    filter_suffix       = ".jpg"
  }
}
