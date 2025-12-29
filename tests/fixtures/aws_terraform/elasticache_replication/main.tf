# ElastiCache Replication Group Test Fixture
# Tests: Multi-AZ Redis replication group with automatic failover

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

# VPC and Networking
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "replication-vpc"
  }
}

resource "aws_subnet" "cache_a" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.1.0/24"
  availability_zone = "us-east-1a"

  tags = {
    Name = "cache-subnet-a"
  }
}

resource "aws_subnet" "cache_b" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.2.0/24"
  availability_zone = "us-east-1b"

  tags = {
    Name = "cache-subnet-b"
  }
}

resource "aws_subnet" "cache_c" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.3.0/24"
  availability_zone = "us-east-1c"

  tags = {
    Name = "cache-subnet-c"
  }
}

# ElastiCache Subnet Group spanning 3 AZs
resource "aws_elasticache_subnet_group" "redis" {
  name       = "redis-replication-subnet-group"
  subnet_ids = [
    aws_subnet.cache_a.id,
    aws_subnet.cache_b.id,
    aws_subnet.cache_c.id
  ]

  tags = {
    Name = "Redis Replication Subnet Group"
  }
}

# Security Group
resource "aws_security_group" "redis" {
  name        = "redis-replication-sg"
  description = "Security group for Redis replication group"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
    description = "Redis access from VPC"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "redis-replication-security-group"
  }
}

# ElastiCache Replication Group (Primary + 2 Replicas across 3 AZs)
resource "aws_elasticache_replication_group" "redis" {
  replication_group_id = "redis-replication"
  description          = "Redis cluster with automatic failover"

  engine               = "redis"
  engine_version       = "7.0"
  node_type            = "cache.t3.micro"
  port                 = 6379
  parameter_group_name = "default.redis7"

  # Multi-AZ with automatic failover
  num_cache_clusters         = 3
  automatic_failover_enabled = true
  multi_az_enabled          = true

  subnet_group_name  = aws_elasticache_subnet_group.redis.name
  security_group_ids = [aws_security_group.redis.id]

  # Maintenance and backup
  snapshot_retention_limit = 5
  snapshot_window         = "03:00-05:00"
  maintenance_window      = "sun:05:00-sun:07:00"

  tags = {
    Name        = "Redis Replication Group"
    Environment = "production"
  }
}

# Lambda function that reads from Redis
resource "aws_iam_role" "lambda" {
  name = "lambda-redis-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_vpc" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_lambda_function" "cache_reader" {
  filename      = "lambda.zip"
  function_name = "redis-cache-reader"
  role          = aws_iam_role.lambda.arn
  handler       = "index.handler"
  runtime       = "python3.11"

  vpc_config {
    subnet_ids         = [aws_subnet.cache_a.id, aws_subnet.cache_b.id]
    security_group_ids = [aws_security_group.redis.id]
  }

  environment {
    variables = {
      REDIS_ENDPOINT = aws_elasticache_replication_group.redis.primary_endpoint_address
      REDIS_PORT     = "6379"
    }
  }

  tags = {
    Name = "Cache Reader Lambda"
  }
}

# Lambda function that writes to Redis
resource "aws_lambda_function" "cache_writer" {
  filename      = "lambda.zip"
  function_name = "redis-cache-writer"
  role          = aws_iam_role.lambda.arn
  handler       = "index.handler"
  runtime       = "python3.11"

  vpc_config {
    subnet_ids         = [aws_subnet.cache_a.id, aws_subnet.cache_b.id]
    security_group_ids = [aws_security_group.redis.id]
  }

  environment {
    variables = {
      REDIS_ENDPOINT = aws_elasticache_replication_group.redis.primary_endpoint_address
      REDIS_PORT     = "6379"
    }
  }

  tags = {
    Name = "Cache Writer Lambda"
  }
}
