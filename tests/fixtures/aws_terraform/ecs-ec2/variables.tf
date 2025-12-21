variable "region" {
  default = "us-east-1"
}

variable "cluster_name" {
  default = "test-ecs-cluster"
}

variable "instance_type" {
  default = "t3.medium"
}

variable "min_capacity" {
  default = 1
}

variable "desired_capacity" {
  default = 2
}

variable "max_capacity" {
  default = 5
}

variable "cpu_target" {
  default = 70
}

variable "memory_target" {
  default = 80
}
