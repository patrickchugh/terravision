# GCP Terraform Test Fixture
# Purpose: Test GCP provider detection and diagram generation

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = "terravision-test-project"
  region  = "us-central1"
}

# VPC Network
resource "google_compute_network" "test" {
  name                    = "terravision-test-vpc"
  auto_create_subnetworks = false
  description             = "Test VPC for TerraVision"
}

# Subnet
resource "google_compute_subnetwork" "test" {
  name          = "terravision-test-subnet"
  ip_cidr_range = "10.0.1.0/24"
  region        = "us-central1"
  network       = google_compute_network.test.id
  description   = "Test subnet for TerraVision"
}

# Firewall Rule - Allow SSH
resource "google_compute_firewall" "allow_ssh" {
  name    = "terravision-test-allow-ssh"
  network = google_compute_network.test.name

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["ssh-enabled"]
}

# Firewall Rule - Allow HTTP/HTTPS
resource "google_compute_firewall" "allow_http" {
  name    = "terravision-test-allow-http"
  network = google_compute_network.test.name

  allow {
    protocol = "tcp"
    ports    = ["80", "443"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["web-server"]
}

# Compute Instance
resource "google_compute_instance" "test" {
  name         = "terravision-test-vm"
  machine_type = "e2-micro"
  zone         = "us-central1-a"

  tags = ["ssh-enabled", "web-server"]

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-11"
      size  = 10
      type  = "pd-standard"
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.test.id

    access_config {
      # Ephemeral public IP
    }
  }

  metadata = {
    environment = "test"
    purpose     = "terravision-fixture"
  }

  service_account {
    scopes = ["cloud-platform"]
  }
}

# Cloud Storage Bucket
resource "google_storage_bucket" "test" {
  name          = "terravision-test-bucket"
  location      = "US"
  force_destroy = true

  uniform_bucket_level_access = true

  labels = {
    environment = "test"
    purpose     = "terravision-fixture"
  }
}

# Cloud Storage Bucket Object
resource "google_storage_bucket_object" "test" {
  name   = "test-file.txt"
  bucket = google_storage_bucket.test.name
  content = "TerraVision Test File"
}

# Persistent Disk
resource "google_compute_disk" "test" {
  name = "terravision-test-disk"
  type = "pd-standard"
  zone = "us-central1-a"
  size = 10

  labels = {
    environment = "test"
  }
}

# Disk Attachment
resource "google_compute_attached_disk" "test" {
  disk     = google_compute_disk.test.id
  instance = google_compute_instance.test.id
}

# Cloud SQL Instance
resource "google_sql_database_instance" "test" {
  name             = "terravision-test-db"
  database_version = "POSTGRES_14"
  region           = "us-central1"

  settings {
    tier = "db-f1-micro"

    ip_configuration {
      ipv4_enabled = true
      authorized_networks {
        name  = "all"
        value = "0.0.0.0/0"
      }
    }

    backup_configuration {
      enabled = false
    }
  }

  deletion_protection = false
}

# Cloud SQL Database
resource "google_sql_database" "test" {
  name     = "terravision-test-database"
  instance = google_sql_database_instance.test.name
}
