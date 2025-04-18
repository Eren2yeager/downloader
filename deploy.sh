#!/bin/bash

# Stop any running instances
pkill -f gunicorn

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    python -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install/update dependencies
pip install -r requirements.txt
pip install gunicorn

# Create download directory if it doesn't exist
mkdir -p yt_downloads

# Set environment variables
export FLASK_ENV=production
export DOWNLOAD_FOLDER=$(pwd)/yt_downloads

# Start the application with Gunicorn
gunicorn app:app --bind 0.0.0.0:8000 --workers 4 --timeout 120 --access-logfile - --error-logfile - 