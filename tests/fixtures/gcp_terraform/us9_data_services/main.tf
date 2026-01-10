# US9: Data Services Test Fixture
# Tests: Cloud SQL, BigQuery, Spanner, Memorystore
# Expected: Regional data services with connections to compute

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

# VPC Network for private services
resource "google_compute_network" "main" {
  name                    = "main-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "app" {
  name          = "app-subnet"
  ip_cidr_range = "10.1.0.0/24"
  region        = "us-central1"
  network       = google_compute_network.main.id
}

# Cloud SQL PostgreSQL instance
resource "google_sql_database_instance" "postgres" {
  name             = "main-postgres"
  database_version = "POSTGRES_14"
  region           = "us-central1"

  settings {
    tier = "db-f1-micro"

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.main.id
    }
  }

  deletion_protection = false
}

# Cloud SQL Database
resource "google_sql_database" "app_db" {
  name     = "app-database"
  instance = google_sql_database_instance.postgres.name
}

# Cloud SQL User
resource "google_sql_user" "app_user" {
  name     = "app-user"
  instance = google_sql_database_instance.postgres.name
  password = "changeme"
}

# Memorystore Redis instance
resource "google_redis_instance" "cache" {
  name           = "app-cache"
  tier           = "STANDARD_HA"
  memory_size_gb = 1
  region         = "us-central1"

  authorized_network = google_compute_network.main.id
}

# BigQuery dataset for analytics
resource "google_bigquery_dataset" "analytics" {
  dataset_id = "analytics"
  location   = "US"
}

# BigQuery table
resource "google_bigquery_table" "events" {
  dataset_id = google_bigquery_dataset.analytics.dataset_id
  table_id   = "events"

  schema = jsonencode([
    {
      name = "event_id"
      type = "STRING"
    },
    {
      name = "timestamp"
      type = "TIMESTAMP"
    }
  ])
}

# Spanner instance
resource "google_spanner_instance" "main" {
  name         = "main-spanner"
  config       = "regional-us-central1"
  display_name = "Main Spanner Instance"
  num_nodes    = 1
}

# Spanner database
resource "google_spanner_database" "app" {
  instance = google_spanner_instance.main.name
  name     = "app-database"
  ddl = [
    "CREATE TABLE Users (UserId INT64 NOT NULL) PRIMARY KEY(UserId)"
  ]
  deletion_protection = false
}

# Application instance connecting to all data services
resource "google_compute_instance" "app" {
  name         = "app-server"
  machine_type = "e2-medium"
  zone         = "us-central1-a"

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-11"
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.app.id
  }

  metadata = {
    postgres_host = google_sql_database_instance.postgres.private_ip_address
    redis_host    = google_redis_instance.cache.host
  }
}
