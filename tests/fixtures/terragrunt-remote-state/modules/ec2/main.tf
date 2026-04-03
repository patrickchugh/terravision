variable "subnet_id" {
  type = string
}

variable "environment" {
  type    = string
  default = "staging"
}

resource "aws_instance" "web" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t3.micro"
  subnet_id     = var.subnet_id

  tags = {
    Name        = "web-${var.environment}"
    Environment = var.environment
  }
}

resource "aws_security_group" "web" {
  name   = "web-sg-${var.environment}"
  vpc_id = "vpc-placeholder"

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "web-sg-${var.environment}"
  }
}
