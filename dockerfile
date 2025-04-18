# Use an official Python image as a base with security updates
FROM python:3.10-slim-bookworm

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FLASK_ENV=production

# Install system dependencies and cleanup in the same layer
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    ca-certificates \
    openssl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    update-ca-certificates

# Set working directory
WORKDIR /app

# Create downloads directory with proper permissions
RUN mkdir -p /app/downloads && chmod 755 /app/downloads

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Set proper permissions and create non-root user
RUN useradd -r -u 1001 appuser && \
    chown -R appuser:appuser /app && \
    chmod -R 755 /app

USER appuser

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]

