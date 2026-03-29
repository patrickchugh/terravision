variable "subnet_id" {
  type = string
}

resource "aws_instance" "web" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t2.micro"
  subnet_id     = var.subnet_id

  tags = {
    Name = "test-instance"
  }
}

resource "aws_security_group" "web" {
  name   = "web-sg"
  vpc_id = var.subnet_id # simplified — in reality derived from subnet's vpc

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
