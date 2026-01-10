# US12: Terraform Registry Module Test - Regional External TCP/UDP (Network) Load Balancer
# Tests: terraform-google-modules/lb/google module
# Expected: Regional external load balancer hierarchy from official Google Terraform module

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
  name                    = "nlb-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "subnet" {
  name          = "nlb-subnet"
  ip_cidr_range = "10.0.0.0/24"
  region        = "us-central1"
  network       = google_compute_network.vpc.id
}

# Instance template for backend
resource "google_compute_instance_template" "backend" {
  name_prefix  = "nlb-backend-"
  machine_type = "e2-medium"
  region       = "us-central1"

  disk {
    source_image = "debian-cloud/debian-11"
    auto_delete  = true
    boot         = true
  }

  network_interface {
    subnetwork = google_compute_subnetwork.subnet.id
    access_config {}
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Instance group manager for backend
resource "google_compute_instance_group_manager" "backend" {
  name               = "nlb-backend-igm"
  base_instance_name = "nlb-backend"
  zone               = "us-central1-a"
  target_size        = 2

  version {
    instance_template = google_compute_instance_template.backend.id
  }
}

# Regional External TCP/UDP (Network) Load Balancer using official Google module
module "gce-nlb" {
  source  = "terraform-google-modules/lb/google"
  version = "~> 4.0"

  project           = "test-project"
  region            = "us-central1"
  name              = "network-lb"
  service_port      = 80
  target_tags       = ["backend"]
  network           = google_compute_network.vpc.name

  target_service_accounts = null

  health_check = {
    check_interval_sec  = 10
    healthy_threshold   = 3
    timeout_sec         = 5
    unhealthy_threshold = 3
    port                = 80
    host                = null
    request_path        = "/"
  }
}

# Target pool for backend instances
resource "google_compute_target_pool" "backend" {
  name   = "backend-pool"
  region = "us-central1"
}

# Outputs
output "external_lb_ip" {
  value = module.gce-nlb.external_ip
}
