# US10: Terraform Registry Module Test - Global HTTP(S) Load Balancer
# Tests: terraform-google-modules/lb-http/google module
# Expected: Load balancer hierarchy from official Google Terraform module

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
  name                    = "lb-http-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "subnet" {
  name          = "lb-http-subnet"
  ip_cidr_range = "10.0.0.0/24"
  region        = "us-central1"
  network       = google_compute_network.vpc.id
}

# Instance template for backend
resource "google_compute_instance_template" "backend" {
  name_prefix  = "backend-"
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

  metadata = {
    startup-script = <<-EOF
      #!/bin/bash
      apt-get update
      apt-get install -y apache2
      echo "Hello from backend" > /var/www/html/index.html
      systemctl start apache2
    EOF
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Instance group manager
resource "google_compute_instance_group_manager" "backend" {
  name               = "backend-igm"
  base_instance_name = "backend"
  zone               = "us-central1-a"
  target_size        = 2

  version {
    instance_template = google_compute_instance_template.backend.id
  }

  named_port {
    name = "http"
    port = 80
  }
}

# Global HTTP(S) Load Balancer using official Google module
module "gce-lb-http" {
  source  = "terraform-google-modules/lb-http/google"
  version = "~> 10.0"

  project = "test-project"
  name    = "http-lb"

  ssl                             = false
  create_url_map                  = true
  https_redirect                  = false
  firewall_networks               = [google_compute_network.vpc.name]
  target_tags                     = ["backend"]

  backends = {
    default = {
      protocol    = "HTTP"
      port        = 80
      port_name   = "http"
      timeout_sec = 30
      enable_cdn  = false

      health_check = {
        request_path = "/"
        port         = 80
      }

      log_config = {
        enable      = true
        sample_rate = 1.0
      }

      groups = [
        {
          group = google_compute_instance_group_manager.backend.instance_group
        }
      ]

      iap_config = {
        enable = false
      }
    }
  }
}

# Outputs
output "load_balancer_ip" {
  value = module.gce-lb-http.external_ip
}
