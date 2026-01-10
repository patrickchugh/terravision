output "load_balancer_ip" {
  description = "External IP of the load balancer"
  value       = google_compute_global_address.lb.address
}

output "database_connection_name" {
  description = "Cloud SQL connection name"
  value       = google_sql_database_instance.main.connection_name
}

output "redis_host" {
  description = "Memorystore Redis host"
  value       = google_redis_instance.cache.host
}

output "static_assets_bucket" {
  description = "Static assets bucket URL"
  value       = google_storage_bucket.static_assets.url
}

output "vpc_network_name" {
  description = "VPC network name"
  value       = google_compute_network.main.name
}
