# US3: GCP Load Balancing Architecture
# Tests: Forwarding Rule → Backend Service → Instance Group → Instances traffic flow

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
  name                    = "lb-vpc"
  auto_create_subnetworks = false
}

# Subnet
resource "google_compute_subnetwork" "subnet" {
  name          = "lb-subnet"
  network       = google_compute_network.vpc.id
  region        = "us-central1"
  ip_cidr_range = "10.0.0.0/24"
}

# Instance Template for backend instances
resource "google_compute_instance_template" "web" {
  name         = "web-template"
  machine_type = "e2-medium"
  region       = "us-central1"

  disk {
    source_image = "debian-cloud/debian-11"
    boot         = true
  }

  network_interface {
    subnetwork = google_compute_subnetwork.subnet.id
  }

  metadata = {
    startup-script = "apt-get update && apt-get install -y nginx"
  }

  tags = ["http-server", "web"]
}

# Managed Instance Group (backend for load balancer)
resource "google_compute_instance_group_manager" "web_igm" {
  name               = "web-igm"
  base_instance_name = "web"
  zone               = "us-central1-a"
  target_size        = 2

  version {
    instance_template = google_compute_instance_template.web.id
  }

  named_port {
    name = "http"
    port = 80
  }
}

# Health Check
resource "google_compute_health_check" "http" {
  name               = "http-health-check"
  check_interval_sec = 5
  timeout_sec        = 5

  http_health_check {
    port = 80
  }
}

# Backend Service
resource "google_compute_backend_service" "web" {
  name                  = "web-backend"
  protocol              = "HTTP"
  port_name             = "http"
  timeout_sec           = 30
  health_checks         = [google_compute_health_check.http.id]

  backend {
    group = google_compute_instance_group_manager.web_igm.instance_group
  }
}

# URL Map
resource "google_compute_url_map" "web" {
  name            = "web-url-map"
  default_service = google_compute_backend_service.web.id
}

# Target HTTP Proxy
resource "google_compute_target_http_proxy" "web" {
  name    = "web-http-proxy"
  url_map = google_compute_url_map.web.id
}

# Global Forwarding Rule (entry point)
resource "google_compute_global_forwarding_rule" "web" {
  name       = "web-forwarding-rule"
  target     = google_compute_target_http_proxy.web.id
  port_range = "80"
}
