# US8: VPC and Firewall Rules Test Fixture
# Tests: VPC hierarchy, firewall rules at VPC level, multiple subnets
# Expected: VPC→Region→Subnet hierarchy, firewall consolidation

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

# VPC Network
resource "google_compute_network" "main" {
  name                    = "main-vpc"
  auto_create_subnetworks = false
}

# Web tier subnet
resource "google_compute_subnetwork" "web" {
  name          = "web-subnet"
  ip_cidr_range = "10.1.0.0/24"
  region        = "us-central1"
  network       = google_compute_network.main.id
}

# App tier subnet
resource "google_compute_subnetwork" "app" {
  name          = "app-subnet"
  ip_cidr_range = "10.2.0.0/24"
  region        = "us-central1"
  network       = google_compute_network.main.id
}

# Database tier subnet
resource "google_compute_subnetwork" "db" {
  name          = "db-subnet"
  ip_cidr_range = "10.3.0.0/24"
  region        = "us-central1"
  network       = google_compute_network.main.id
}

# Allow HTTP/HTTPS from internet to web tier
resource "google_compute_firewall" "allow_http" {
  name    = "allow-http"
  network = google_compute_network.main.name

  allow {
    protocol = "tcp"
    ports    = ["80", "443"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["web"]
}

# Allow SSH from corporate network
resource "google_compute_firewall" "allow_ssh" {
  name    = "allow-ssh"
  network = google_compute_network.main.name

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["10.0.0.0/8"]
  target_tags   = ["bastion"]
}

# Allow app tier to talk to db tier
resource "google_compute_firewall" "allow_app_to_db" {
  name    = "allow-app-to-db"
  network = google_compute_network.main.name

  allow {
    protocol = "tcp"
    ports    = ["5432", "3306"]
  }

  source_tags = ["app"]
  target_tags = ["db"]
}

# Internal communication
resource "google_compute_firewall" "allow_internal" {
  name    = "allow-internal"
  network = google_compute_network.main.name

  allow {
    protocol = "tcp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "udp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "icmp"
  }

  source_ranges = ["10.0.0.0/8"]
}

# Web server instance
resource "google_compute_instance" "web" {
  name         = "web-server"
  machine_type = "e2-medium"
  zone         = "us-central1-a"

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-11"
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.web.id
    access_config {}
  }

  tags = ["web"]
}

# App server instance
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

  tags = ["app"]
}
