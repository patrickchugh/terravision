resource "aws_s3_bucket" "example" {
  bucket = "terravision-test-bucket"

  tags = {
    Name = "test-bucket"
  }
}
