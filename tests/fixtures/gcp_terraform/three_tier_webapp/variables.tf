variable "project_id" {
  description = "GCP Project ID"
  type        = string
  default     = "my-gcp-project"
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "us-central1"
}

variable "db_password" {
  description = "Database password"
  type        = string
  sensitive   = true
  default     = "changeme123!"
}
