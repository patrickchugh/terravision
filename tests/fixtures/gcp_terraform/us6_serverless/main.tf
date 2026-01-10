# US6: Serverless Architecture Test Fixture
# Tests: Cloud Functions and Cloud Run with triggers and connections
# Expected: Functions/Run connected to triggers, storage, and Pub/Sub

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

# Storage bucket for function source code
resource "google_storage_bucket" "function_source" {
  name          = "test-project-function-source"
  location      = "US"
  force_destroy = true
}

# Storage bucket for data processing
resource "google_storage_bucket" "data_bucket" {
  name          = "test-project-data-processing"
  location      = "US"
  force_destroy = true
}

# Pub/Sub topic for events
resource "google_pubsub_topic" "events" {
  name = "events-topic"
}

# Cloud Function (Gen 2) - HTTP triggered
resource "google_cloudfunctions2_function" "http_function" {
  name     = "http-function"
  location = "us-central1"

  build_config {
    runtime     = "python311"
    entry_point = "handle_request"

    source {
      storage_source {
        bucket = google_storage_bucket.function_source.name
        object = "function-source.zip"
      }
    }
  }

  service_config {
    max_instance_count = 10
    available_memory   = "256M"
    timeout_seconds    = 60
  }
}

# Cloud Function - Pub/Sub triggered
resource "google_cloudfunctions2_function" "pubsub_function" {
  name     = "pubsub-function"
  location = "us-central1"

  build_config {
    runtime     = "python311"
    entry_point = "process_message"

    source {
      storage_source {
        bucket = google_storage_bucket.function_source.name
        object = "function-source.zip"
      }
    }
  }

  service_config {
    max_instance_count = 5
    available_memory   = "512M"
    timeout_seconds    = 120
  }

  event_trigger {
    trigger_region = "us-central1"
    event_type     = "google.cloud.pubsub.topic.v1.messagePublished"
    pubsub_topic   = google_pubsub_topic.events.id
    retry_policy   = "RETRY_POLICY_RETRY"
  }
}

# Cloud Run service
resource "google_cloud_run_service" "api" {
  name     = "api-service"
  location = "us-central1"

  template {
    spec {
      containers {
        image = "gcr.io/test-project/api:latest"

        env {
          name  = "DATA_BUCKET"
          value = google_storage_bucket.data_bucket.name
        }
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }
}

# IAM - Make Cloud Run service public
resource "google_cloud_run_service_iam_member" "public" {
  location = google_cloud_run_service.api.location
  service  = google_cloud_run_service.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
