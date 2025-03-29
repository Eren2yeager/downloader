# Use a recent version of Ubuntu
FROM ubuntu:24.04

# Install necessary packages
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    ffmpeg \
    && apt-get clean

# Set the working directory
WORKDIR /app

# Copy your application code
COPY . .

# Install Python dependencies
RUN pip3 install -r requirements.txt

# Command to run your application
CMD ["python3", "app.py"]