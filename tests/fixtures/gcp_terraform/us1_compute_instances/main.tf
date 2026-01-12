# User Story 1: Compute Instance Visualization
# Tests: VPC → Region → Subnet → Zone → Instance hierarchy
# Instances in different zones (us-central1-a and us-central1-b)

terraform {
  required_version = ">= 1.0"
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

# VPC Network (global)
resource "google_compute_network" "main_vpc" {
  name                    = "main-vpc"
  auto_create_subnetworks = false
}

# Subnet (regional resource in us-central1)
resource "google_compute_subnetwork" "main_subnet" {
  name          = "main-subnet"
  ip_cidr_range = "10.0.1.0/24"
  region        = "us-central1"
  network       = google_compute_network.main_vpc.id
}

# Compute Instance in Zone A
resource "google_compute_instance" "web_server_a" {
  name         = "web-server-a"
  machine_type = "e2-medium"
  zone         = "us-central1-a"

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-11"
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.main_subnet.id
  }

  metadata = {
    startup-script = "#!/bin/bash\necho 'Web Server A' > /var/www/html/index.html"
  }

  tags = ["web", "zone-a"]
}

# Compute Instance in Zone B
resource "google_compute_instance" "web_server_b" {
  name         = "web-server-b"
  machine_type = "e2-medium"
  zone         = "us-central1-b"

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-11"
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.main_subnet.id
  }

  metadata = {
    startup-script = "#!/bin/bash\necho 'Web Server B' > /var/www/html/index.html"
  }

  tags = ["web", "zone-b"]
}

# Outputs for verification
output "vpc_id" {
  value       = google_compute_network.main_vpc.id
  description = "VPC network ID"
}

output "subnet_id" {
  value       = google_compute_subnetwork.main_subnet.id
  description = "Subnet ID"
}

output "instance_a_zone" {
  value       = google_compute_instance.web_server_a.zone
  description = "Instance A zone"
}

output "instance_b_zone" {
  value       = google_compute_instance.web_server_b.zone
  description = "Instance B zone"
}
