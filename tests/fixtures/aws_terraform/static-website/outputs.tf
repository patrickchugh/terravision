output "cloudfront_distribution_domain_name" {
  description = "CloudFront distribution domain name"
  value       = module.cloudfront.cloudfront_distribution_domain_name
}

output "s3_bucket_name" {
  description = "S3 bucket name"
  value       = module.s3_bucket.s3_bucket_id
}

output "website_url" {
  description = "Website URL"
  value       = "https://${module.cloudfront.cloudfront_distribution_domain_name}"
}
