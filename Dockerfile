# Use the latest Ubuntu base image
FROM ubuntu:latest

# Install Graphviz and other dependencies
RUN apt-get update && apt-get install -y graphviz git python3-pip python-is-python3

# Set the working directory to the Terravision directory
WORKDIR /app/

# Install Terravision dependencies from requirements.txt
COPY . .
RUN pip install -r requirements.txt

# Grant execution permission to the terravision script
RUN chmod +x terravision

# Default command to be executed when the container starts
CMD ["./terravision"]