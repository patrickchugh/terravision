# US11: Internal Load Balancer Test Fixture (equivalent to terraform-google-modules/lb-internal/google)
# Tests: Regional internal TCP/UDP load balancing resources
# Expected: Internal LB with forwarding rule, backend service, health check
# Note: Uses native resources instead of module because lb-internal module requires GCP API access for data sources

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
resource "google_compute_network" "vpc" {
  name                    = "ilb-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "subnet" {
  name          = "ilb-subnet"
  ip_cidr_range = "10.0.0.0/24"
  region        = "us-central1"
  network       = google_compute_network.vpc.id
}

# Instance template for backend
resource "google_compute_instance_template" "backend" {
  name_prefix  = "ilb-backend-"
  machine_type = "e2-medium"
  region       = "us-central1"

  disk {
    source_image = "debian-cloud/debian-11"
    auto_delete  = true
    boot         = true
  }

  network_interface {
    subnetwork = google_compute_subnetwork.subnet.id
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Instance group manager for backend
resource "google_compute_instance_group_manager" "backend" {
  name               = "ilb-backend-igm"
  base_instance_name = "ilb-backend"
  zone               = "us-central1-a"
  target_size        = 2

  version {
    instance_template = google_compute_instance_template.backend.id
  }

  named_port {
    name = "tcp"
    port = 80
  }
}

# Health check for internal load balancer
resource "google_compute_health_check" "internal" {
  name = "internal-health-check"

  tcp_health_check {
    port = 80
  }

  check_interval_sec  = 10
  healthy_threshold   = 2
  timeout_sec         = 5
  unhealthy_threshold = 3
}

# Backend service for internal load balancer
resource "google_compute_region_backend_service" "internal" {
  name          = "internal-backend-service"
  region        = "us-central1"
  protocol      = "TCP"
  health_checks = [google_compute_health_check.internal.id]

  backend {
    group = google_compute_instance_group_manager.backend.instance_group
  }
}

# Internal forwarding rule
resource "google_compute_forwarding_rule" "internal" {
  name                  = "internal-forwarding-rule"
  region                = "us-central1"
  load_balancing_scheme = "INTERNAL"
  backend_service       = google_compute_region_backend_service.internal.id
  ports                 = ["80"]
  network               = google_compute_network.vpc.id
  subnetwork            = google_compute_subnetwork.subnet.id
}

# Firewall rule for internal load balancer
resource "google_compute_firewall" "allow_ilb" {
  name    = "allow-ilb-health-check"
  network = google_compute_network.vpc.name

  allow {
    protocol = "tcp"
    ports    = ["80"]
  }

  # Google health check ranges
  source_ranges = ["130.211.0.0/22", "35.191.0.0/16"]
  target_tags   = ["backend"]
}

# Client instance connecting to the internal LB
resource "google_compute_instance" "client" {
  name         = "client-vm"
  machine_type = "e2-micro"
  zone         = "us-central1-a"

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-11"
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.subnet.id
  }

  tags = ["client"]
}
