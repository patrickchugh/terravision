output "cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "autoscaling_group_name" {
  value = aws_autoscaling_group.ecs.name
}
