# US2: Instance Group Manager with Synthetic Managed Instances
# Tests: IGM with target_size=3 creates synthetic instances (instance~1, instance~2, instance~3)

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

# VPC Network (global)
resource "google_compute_network" "vpc" {
  name                    = "test-vpc"
  auto_create_subnetworks = false
}

# Subnet (regional)
resource "google_compute_subnetwork" "subnet" {
  name          = "test-subnet"
  network       = google_compute_network.vpc.id
  region        = "us-central1"
  ip_cidr_range = "10.0.0.0/24"
}

# Instance Template (regional - should appear at region level, not zone)
resource "google_compute_instance_template" "web" {
  name         = "web-template"
  machine_type = "n1-standard-2"
  region       = "us-central1"

  disk {
    source_image = "debian-cloud/debian-11"
    boot         = true
  }

  network_interface {
    subnetwork = google_compute_subnetwork.subnet.id
  }

  metadata = {
    startup-script = "echo 'Hello, World!'"
  }

  tags = ["web", "http-server"]
}

# Zonal Instance Group Manager with target_size=3
# This should create 3 synthetic instances: web~1, web~2, web~3
resource "google_compute_instance_group_manager" "igm" {
  name               = "web-igm"
  base_instance_name = "web"
  zone               = "us-central1-a"
  target_size        = 3

  version {
    instance_template = google_compute_instance_template.web.id
  }

  named_port {
    name = "http"
    port = 80
  }
}
