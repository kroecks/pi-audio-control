FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    pulseaudio-utils \
    bluez \
    bluetooth \
    dbus \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8080

# Run the application
CMD ["python", "main.py"]