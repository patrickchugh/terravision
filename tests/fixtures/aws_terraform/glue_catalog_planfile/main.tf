provider "aws" {
  region = "us-east-1"
}

resource "aws_s3_bucket" "reports" {
  bucket = "example-reports"
}

resource "aws_glue_catalog_database" "analytics" {
  name = "analytics"
}

resource "aws_glue_catalog_table" "report" {
  name          = "report"
  database_name = aws_glue_catalog_database.analytics.name
  table_type    = "EXTERNAL_TABLE"

  storage_descriptor {
    location = "s3://${aws_s3_bucket.reports.bucket}/report/"
  }
}
