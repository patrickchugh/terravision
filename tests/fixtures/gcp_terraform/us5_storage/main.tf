# US5: Cloud Storage & IAM Test Fixture
# Tests: Storage bucket hierarchy and IAM connections
# Expected: Storage buckets with IAM policies, service accounts

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = "test-project"
  region  = "us-central1"
}

# Service Account for application
resource "google_service_account" "app_sa" {
  account_id   = "app-service-account"
  display_name = "Application Service Account"
}

# Primary data bucket
resource "google_storage_bucket" "data" {
  name          = "test-project-data"
  location      = "US"
  force_destroy = true

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type = "Delete"
    }
  }
}

# Backup bucket
resource "google_storage_bucket" "backup" {
  name          = "test-project-backup"
  location      = "US"
  force_destroy = true
  storage_class = "NEARLINE"
}

# Static assets bucket
resource "google_storage_bucket" "static" {
  name          = "test-project-static"
  location      = "US"
  force_destroy = true

  website {
    main_page_suffix = "index.html"
    not_found_page   = "404.html"
  }
}

# IAM binding for data bucket
resource "google_storage_bucket_iam_member" "data_viewer" {
  bucket = google_storage_bucket.data.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.app_sa.email}"
}

# IAM binding for backup bucket (admin access)
resource "google_storage_bucket_iam_member" "backup_admin" {
  bucket = google_storage_bucket.backup.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.app_sa.email}"
}

# Compute instance using the service account
resource "google_compute_instance" "app_server" {
  name         = "app-server"
  machine_type = "e2-medium"
  zone         = "us-central1-a"

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-11"
    }
  }

  network_interface {
    network = "default"
  }

  service_account {
    email  = google_service_account.app_sa.email
    scopes = ["cloud-platform"]
  }
}
