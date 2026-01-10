# Three-Tier Web Application on Google Cloud Platform
# Architecture: Load Balancer -> Web Tier -> App Tier -> Database Tier

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# =============================================================================
# VPC Network
# =============================================================================

resource "google_compute_network" "main" {
  name                    = "three-tier-vpc"
  auto_create_subnetworks = false
  description             = "VPC for three-tier web application"
}

# =============================================================================
# Subnets
# =============================================================================

resource "google_compute_subnetwork" "web" {
  name          = "web-subnet"
  ip_cidr_range = "10.0.1.0/24"
  region        = var.region
  network       = google_compute_network.main.id
  description   = "Subnet for web tier"
}

resource "google_compute_subnetwork" "app" {
  name          = "app-subnet"
  ip_cidr_range = "10.0.2.0/24"
  region        = var.region
  network       = google_compute_network.main.id
  description   = "Subnet for application tier"
}

resource "google_compute_subnetwork" "db" {
  name          = "db-subnet"
  ip_cidr_range = "10.0.3.0/24"
  region        = var.region
  network       = google_compute_network.main.id
  description   = "Subnet for database tier"
}

# =============================================================================
# Firewall Rules
# =============================================================================

resource "google_compute_firewall" "allow_http" {
  name    = "allow-http"
  network = google_compute_network.main.name

  allow {
    protocol = "tcp"
    ports    = ["80", "443"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["web-server"]
}

resource "google_compute_firewall" "allow_app" {
  name    = "allow-app"
  network = google_compute_network.main.name

  allow {
    protocol = "tcp"
    ports    = ["8080"]
  }

  source_tags = ["web-server"]
  target_tags = ["app-server"]
}

resource "google_compute_firewall" "allow_db" {
  name    = "allow-db"
  network = google_compute_network.main.name

  allow {
    protocol = "tcp"
    ports    = ["5432"]
  }

  source_tags = ["app-server"]
  target_tags = ["db-server"]
}

resource "google_compute_firewall" "allow_ssh" {
  name    = "allow-ssh"
  network = google_compute_network.main.name

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["35.235.240.0/20"] # IAP range
  target_tags   = ["ssh-enabled"]
}

# =============================================================================
# Web Tier - Instance Template and Managed Instance Group
# =============================================================================

resource "google_compute_instance_template" "web" {
  name_prefix  = "web-template-"
  machine_type = "e2-medium"
  region       = var.region

  disk {
    source_image = "debian-cloud/debian-11"
    auto_delete  = true
    boot         = true
  }

  network_interface {
    subnetwork = google_compute_subnetwork.web.id
    access_config {
      # Ephemeral public IP
    }
  }

  metadata_startup_script = <<-EOF
    #!/bin/bash
    apt-get update
    apt-get install -y nginx
    systemctl start nginx
  EOF

  tags = ["web-server", "ssh-enabled"]

  lifecycle {
    create_before_destroy = true
  }
}

resource "google_compute_instance_group_manager" "web" {
  name               = "web-instance-group"
  base_instance_name = "web"
  zone               = "${var.region}-a"
  target_size        = 2

  version {
    instance_template = google_compute_instance_template.web.id
  }

  named_port {
    name = "http"
    port = 80
  }
}

# =============================================================================
# Application Tier - Instance Template and Managed Instance Group
# =============================================================================

resource "google_compute_instance_template" "app" {
  name_prefix  = "app-template-"
  machine_type = "e2-medium"
  region       = var.region

  disk {
    source_image = "debian-cloud/debian-11"
    auto_delete  = true
    boot         = true
  }

  network_interface {
    subnetwork = google_compute_subnetwork.app.id
  }

  metadata_startup_script = <<-EOF
    #!/bin/bash
    apt-get update
    apt-get install -y openjdk-11-jre
  EOF

  tags = ["app-server", "ssh-enabled"]

  lifecycle {
    create_before_destroy = true
  }
}

resource "google_compute_instance_group_manager" "app" {
  name               = "app-instance-group"
  base_instance_name = "app"
  zone               = "${var.region}-a"
  target_size        = 2

  version {
    instance_template = google_compute_instance_template.app.id
  }

  named_port {
    name = "app"
    port = 8080
  }
}

# =============================================================================
# Database Tier - Cloud SQL
# =============================================================================

resource "google_sql_database_instance" "main" {
  name             = "main-db-instance"
  database_version = "POSTGRES_14"
  region           = var.region

  settings {
    tier = "db-custom-2-4096"

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.main.id
    }

    backup_configuration {
      enabled    = true
      start_time = "03:00"
    }

    availability_type = "REGIONAL"
  }

  deletion_protection = false
}

resource "google_sql_database" "app_db" {
  name     = "app_database"
  instance = google_sql_database_instance.main.name
}

resource "google_sql_user" "app_user" {
  name     = "app_user"
  instance = google_sql_database_instance.main.name
  password = var.db_password
}

# =============================================================================
# Load Balancer
# =============================================================================

resource "google_compute_global_address" "lb" {
  name = "lb-static-ip"
}

resource "google_compute_health_check" "http" {
  name               = "http-health-check"
  check_interval_sec = 10
  timeout_sec        = 5

  http_health_check {
    port = 80
  }
}

resource "google_compute_backend_service" "web" {
  name                  = "web-backend-service"
  protocol              = "HTTP"
  port_name             = "http"
  timeout_sec           = 30
  health_checks         = [google_compute_health_check.http.id]
  load_balancing_scheme = "EXTERNAL"

  backend {
    group           = google_compute_instance_group_manager.web.instance_group
    balancing_mode  = "UTILIZATION"
    max_utilization = 0.8
  }
}

resource "google_compute_url_map" "web" {
  name            = "web-url-map"
  default_service = google_compute_backend_service.web.id
}

resource "google_compute_target_http_proxy" "web" {
  name    = "web-http-proxy"
  url_map = google_compute_url_map.web.id
}

resource "google_compute_global_forwarding_rule" "http" {
  name                  = "http-forwarding-rule"
  ip_protocol           = "TCP"
  port_range            = "80"
  target                = google_compute_target_http_proxy.web.id
  ip_address            = google_compute_global_address.lb.id
  load_balancing_scheme = "EXTERNAL"
}

# =============================================================================
# Cloud Storage for Static Assets
# =============================================================================

resource "google_storage_bucket" "static_assets" {
  name          = "${var.project_id}-static-assets"
  location      = var.region
  force_destroy = true

  uniform_bucket_level_access = true

  website {
    main_page_suffix = "index.html"
    not_found_page   = "404.html"
  }

  cors {
    origin          = ["*"]
    method          = ["GET", "HEAD"]
    response_header = ["*"]
    max_age_seconds = 3600
  }
}

# =============================================================================
# Cloud CDN via Backend Bucket
# =============================================================================

resource "google_compute_backend_bucket" "static" {
  name        = "static-backend-bucket"
  bucket_name = google_storage_bucket.static_assets.name
  enable_cdn  = true
}

# =============================================================================
# Memorystore Redis for Caching
# =============================================================================

resource "google_redis_instance" "cache" {
  name           = "app-cache"
  tier           = "STANDARD_HA"
  memory_size_gb = 1
  region         = var.region

  authorized_network = google_compute_network.main.id

  redis_version = "REDIS_6_X"
  display_name  = "Application Cache"
}

# =============================================================================
# Cloud Monitoring - Uptime Check
# =============================================================================

resource "google_monitoring_uptime_check_config" "http" {
  display_name = "HTTP Uptime Check"
  timeout      = "10s"
  period       = "60s"

  http_check {
    path         = "/"
    port         = 80
    use_ssl      = false
    validate_ssl = false
  }

  monitored_resource {
    type = "uptime_url"
    labels = {
      project_id = var.project_id
      host       = google_compute_global_address.lb.address
    }
  }
}

# =============================================================================
# Cloud Logging Sink
# =============================================================================

resource "google_logging_project_sink" "audit_logs" {
  name        = "audit-logs-sink"
  destination = "storage.googleapis.com/${google_storage_bucket.logs.name}"
  filter      = "logName:\"logs/cloudaudit.googleapis.com\""

  unique_writer_identity = true
}

resource "google_storage_bucket" "logs" {
  name          = "${var.project_id}-audit-logs"
  location      = var.region
  force_destroy = true

  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type = "Delete"
    }
  }
}

resource "google_storage_bucket_iam_member" "logs_writer" {
  bucket = google_storage_bucket.logs.name
  role   = "roles/storage.objectCreator"
  member = google_logging_project_sink.audit_logs.writer_identity
}
