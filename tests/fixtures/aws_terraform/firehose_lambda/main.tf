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

# S3 bucket for Firehose destination
resource "aws_s3_bucket" "destination" {
  bucket = "firehose-delivery-destination"
}

# S3 bucket for Firehose error logs
resource "aws_s3_bucket" "errors" {
  bucket = "firehose-delivery-errors"
}

# IAM role for Lambda transformation function
resource "aws_iam_role" "lambda_role" {
  name = "firehose-lambda-role"

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

# Attach basic Lambda execution policy
resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Lambda function for data transformation
resource "aws_lambda_function" "transform" {
  filename      = "lambda.zip"
  function_name = "firehose-data-transform"
  role          = aws_iam_role.lambda_role.arn
  handler       = "index.handler"
  runtime       = "python3.11"
  timeout       = 60

  environment {
    variables = {
      TRANSFORM_TYPE = "json_to_parquet"
    }
  }
}

# CloudWatch log group for Lambda
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${aws_lambda_function.transform.function_name}"
  retention_in_days = 7
}

# IAM role for Firehose delivery stream
resource "aws_iam_role" "firehose_role" {
  name = "firehose-delivery-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "firehose.amazonaws.com"
        }
      }
    ]
  })
}

# IAM policy for Firehose S3 access
resource "aws_iam_role_policy" "firehose_s3" {
  name = "firehose-s3-access"
  role = aws_iam_role.firehose_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:AbortMultipartUpload",
          "s3:GetBucketLocation",
          "s3:GetObject",
          "s3:ListBucket",
          "s3:ListBucketMultipartUploads",
          "s3:PutObject"
        ]
        Resource = [
          aws_s3_bucket.destination.arn,
          "${aws_s3_bucket.destination.arn}/*",
          aws_s3_bucket.errors.arn,
          "${aws_s3_bucket.errors.arn}/*"
        ]
      }
    ]
  })
}

# IAM policy for Firehose Lambda invocation
resource "aws_iam_role_policy" "firehose_lambda" {
  name = "firehose-lambda-invoke"
  role = aws_iam_role.firehose_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction",
          "lambda:GetFunctionConfiguration"
        ]
        Resource = aws_lambda_function.transform.arn
      }
    ]
  })
}

# Kinesis Firehose delivery stream
resource "aws_kinesis_firehose_delivery_stream" "main" {
  name        = "analytics-delivery-stream"
  destination = "extended_s3"

  extended_s3_configuration {
    role_arn   = aws_iam_role.firehose_role.arn
    bucket_arn = aws_s3_bucket.destination.arn

    prefix              = "data/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/"
    error_output_prefix = "errors/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/!{firehose:error-output-type}/"

    buffering_size     = 5
    buffering_interval = 300
    compression_format = "GZIP"

    processing_configuration {
      enabled = true

      processors {
        type = "Lambda"

        parameters {
          parameter_name  = "LambdaArn"
          parameter_value = "${aws_lambda_function.transform.arn}:$LATEST"
        }

        parameters {
          parameter_name  = "BufferSizeInMBs"
          parameter_value = "3"
        }

        parameters {
          parameter_name  = "BufferIntervalInSeconds"
          parameter_value = "60"
        }
      }
    }

    cloudwatch_logging_options {
      enabled         = true
      log_group_name  = aws_cloudwatch_log_group.firehose_logs.name
      log_stream_name = "S3Delivery"
    }
  }
}

# CloudWatch log group for Firehose
resource "aws_cloudwatch_log_group" "firehose_logs" {
  name              = "/aws/kinesisfirehose/analytics-delivery-stream"
  retention_in_days = 7
}

# CloudWatch log stream for Firehose
resource "aws_cloudwatch_log_stream" "firehose_stream" {
  name           = "S3Delivery"
  log_group_name = aws_cloudwatch_log_group.firehose_logs.name
}
