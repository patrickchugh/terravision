# US7: Pub/Sub Messaging Test Fixture
# Tests: Topics, subscriptions, and push endpoints
# Expected: Topic→Subscription hierarchy, push to Cloud Run/HTTP

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

# Primary event topic
resource "google_pubsub_topic" "events" {
  name = "events-topic"

  message_retention_duration = "86400s"
}

# Dead letter topic
resource "google_pubsub_topic" "dead_letter" {
  name = "events-dead-letter"
}

# Pull subscription for batch processing
resource "google_pubsub_subscription" "batch_processor" {
  name  = "batch-processor"
  topic = google_pubsub_topic.events.name

  ack_deadline_seconds = 60

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dead_letter.id
    max_delivery_attempts = 5
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }
}

# Push subscription to Cloud Run
resource "google_pubsub_subscription" "push_to_api" {
  name  = "push-to-api"
  topic = google_pubsub_topic.events.name

  ack_deadline_seconds = 30

  push_config {
    push_endpoint = "https://api-service-abc123.run.app/events"

    attributes = {
      x-goog-version = "v1"
    }
  }
}

# Cloud Run service receiving push events
resource "google_cloud_run_service" "event_handler" {
  name     = "event-handler"
  location = "us-central1"

  template {
    spec {
      containers {
        image = "gcr.io/test-project/event-handler:latest"
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }
}

# BigQuery sink for analytics
resource "google_pubsub_subscription" "bigquery_sink" {
  name  = "bigquery-sink"
  topic = google_pubsub_topic.events.name

  bigquery_config {
    table            = "${google_bigquery_table.events.project}.${google_bigquery_dataset.analytics.dataset_id}.${google_bigquery_table.events.table_id}"
    write_metadata   = true
    use_topic_schema = false
  }
}

# BigQuery dataset for analytics
resource "google_bigquery_dataset" "analytics" {
  dataset_id = "analytics"
  location   = "US"
}

# BigQuery table for events
resource "google_bigquery_table" "events" {
  dataset_id = google_bigquery_dataset.analytics.dataset_id
  table_id   = "events"

  schema = jsonencode([
    {
      name = "event_id"
      type = "STRING"
      mode = "REQUIRED"
    },
    {
      name = "timestamp"
      type = "TIMESTAMP"
      mode = "REQUIRED"
    },
    {
      name = "data"
      type = "STRING"
      mode = "NULLABLE"
    }
  ])
}
