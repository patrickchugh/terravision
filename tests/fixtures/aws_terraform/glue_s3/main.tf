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

# Source S3 bucket for raw data
resource "aws_s3_bucket" "source" {
  bucket = "glue-etl-source"
}

# Destination S3 bucket for processed data
resource "aws_s3_bucket" "destination" {
  bucket = "glue-etl-destination"
}

# S3 bucket for Glue scripts
resource "aws_s3_bucket" "scripts" {
  bucket = "glue-scripts"
}

# S3 object for Glue job script
resource "aws_s3_object" "etl_script" {
  bucket  = aws_s3_bucket.scripts.id
  key     = "scripts/transform.py"
  content = <<-EOT
    import sys
    from awsglue.transforms import *
    from awsglue.utils import getResolvedOptions
    from pyspark.context import SparkContext
    from awsglue.context import GlueContext
    from awsglue.job import Job

    args = getResolvedOptions(sys.argv, ['JOB_NAME'])
    sc = SparkContext()
    glueContext = GlueContext(sc)
    spark = glueContext.spark_session
    job = Job(glueContext)
    job.init(args['JOB_NAME'], args)

    # Read from source
    datasource = glueContext.create_dynamic_frame.from_options(
        "s3",
        {"paths": ["s3://glue-etl-source/input/"]},
        format="parquet"
    )

    # Transform data
    transformed = ApplyMapping.apply(frame=datasource, mappings=[
        ("id", "string", "id", "string"),
        ("value", "double", "value", "double")
    ])

    # Write to destination
    glueContext.write_dynamic_frame.from_options(
        transformed,
        connection_type="s3",
        connection_options={"path": "s3://glue-etl-destination/output/"},
        format="parquet"
    )

    job.commit()
  EOT
}

# IAM role for Glue job
resource "aws_iam_role" "glue_role" {
  name = "glue-etl-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "glue.amazonaws.com"
        }
      }
    ]
  })
}

# IAM policy for S3 access
resource "aws_iam_role_policy" "glue_s3_policy" {
  name = "glue-s3-access"
  role = aws_iam_role.glue_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]
        Resource = [
          "${aws_s3_bucket.source.arn}/*",
          "${aws_s3_bucket.destination.arn}/*",
          "${aws_s3_bucket.scripts.arn}/*"
        ]
      }
    ]
  })
}

# Attach Glue service policy
resource "aws_iam_role_policy_attachment" "glue_service" {
  role       = aws_iam_role.glue_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

# Glue catalog database
resource "aws_glue_catalog_database" "etl_database" {
  name = "etl_database"
}

# Glue crawler for source data
resource "aws_glue_crawler" "source_crawler" {
  name          = "source-data-crawler"
  database_name = aws_glue_catalog_database.etl_database.name
  role          = aws_iam_role.glue_role.arn

  s3_target {
    path = "s3://${aws_s3_bucket.source.bucket}/input/"
  }
}

# Glue ETL job
resource "aws_glue_job" "etl_job" {
  name     = "data-transformation-job"
  role_arn = aws_iam_role.glue_role.arn

  command {
    name            = "glueetl"
    script_location = "s3://${aws_s3_bucket.scripts.bucket}/${aws_s3_object.etl_script.key}"
    python_version  = "3"
  }

  default_arguments = {
    "--job-language"        = "python"
    "--enable-metrics"      = "true"
    "--enable-spark-ui"     = "true"
    "--enable-job-insights" = "true"
  }

  max_retries       = 1
  timeout           = 60
  glue_version      = "4.0"
  worker_type       = "G.1X"
  number_of_workers = 2
}

# CloudWatch log group for Glue job
resource "aws_cloudwatch_log_group" "glue_logs" {
  name              = "/aws-glue/jobs/${aws_glue_job.etl_job.name}"
  retention_in_days = 7
}
