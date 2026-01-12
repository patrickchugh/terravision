# US4: GKE Cluster Hierarchy Test Fixture
# Tests: Region -> GKE Cluster -> Node Pool hierarchy
# Expected: GKE cluster contains node pools, connected to GCR via auto-annotation

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
  name                    = "gke-vpc"
  auto_create_subnetworks = false
}

# Subnet for GKE
resource "google_compute_subnetwork" "gke_subnet" {
  name          = "gke-subnet"
  ip_cidr_range = "10.0.0.0/16"
  region        = "us-central1"
  network       = google_compute_network.vpc.id

  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = "10.1.0.0/16"
  }

  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = "10.2.0.0/16"
  }
}

# GKE Cluster
resource "google_container_cluster" "primary" {
  name     = "primary-cluster"
  location = "us-central1"

  network    = google_compute_network.vpc.name
  subnetwork = google_compute_subnetwork.gke_subnet.name

  # We can't create a cluster with no node pool defined, but we want to only use
  # separately managed node pools. So we create the smallest possible default
  # node pool and immediately delete it.
  remove_default_node_pool = true
  initial_node_count       = 1

  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "services"
  }
}

# Node Pool 1: General purpose workloads
resource "google_container_node_pool" "general" {
  name       = "general-pool"
  location   = "us-central1"
  cluster    = google_container_cluster.primary.name
  node_count = 2

  node_config {
    machine_type = "e2-medium"
    disk_size_gb = 100

    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]

    labels = {
      workload = "general"
    }
  }
}

# Node Pool 2: High-memory workloads
resource "google_container_node_pool" "highmem" {
  name       = "highmem-pool"
  location   = "us-central1"
  cluster    = google_container_cluster.primary.name
  node_count = 1

  node_config {
    machine_type = "n2-highmem-4"
    disk_size_gb = 200

    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]

    labels = {
      workload = "highmem"
    }
  }
}

# Container Registry (for GKE auto-annotation)
resource "google_container_registry" "gcr" {
  project  = "test-project"
  location = "US"
}
