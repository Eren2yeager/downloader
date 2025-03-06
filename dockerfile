# Use an Ubuntu base image
FROM ubuntu:22.04

# Set working directory
WORKDIR /app

# Install dependencies, including GLIBC
RUN apt update && apt install -y \
    libc6 \
    libc6-dev \
    build-essential \
    bison \
    flex

# Copy your project files
COPY . .

# Set entrypoint (Modify according to your project)
CMD ["gunicorn", "app:app"]
