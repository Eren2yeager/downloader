# Use an official Python image as a base with security updates
FROM python:3.10-slim-bookworm

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FLASK_ENV=production \
    PATH="/home/appuser/.local/bin:${PATH}"

# Install system dependencies and cleanup in the same layer
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    ca-certificates \
    openssl \
    curl \
    gnupg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && update-ca-certificates

# Create non-root user
RUN useradd -m -r -u 1001 appuser && \
    mkdir -p /app /app/downloads /app/temp && \
    chown -R appuser:appuser /app

# Set working directory
WORKDIR /app

# Switch to non-root user
USER appuser

# Copy requirements first to leverage Docker cache
COPY --chown=appuser:appuser requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Copy the application with proper ownership
COPY --chown=appuser:appuser . .

# Set proper permissions
RUN chmod -R 755 /app

# Create required directories with proper permissions
RUN mkdir -p /app/downloads /app/temp && \
    chmod 755 /app/downloads /app/temp

# Expose port
EXPOSE 8080

# Set healthcheck
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/ || exit 1

# Use gunicorn with proper configuration
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "4", "--threads", "2", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "--capture-output", "app:app"]

