FROM python:3.11-slim

# Install system dependencies including build tools for pygobject
RUN apt-get update && apt-get install -y \
    pulseaudio-utils \
    bluez \
    bluetooth \
    dbus \
    gcc \
    pkg-config \
    libcairo2-dev \
    libgirepository1.0-dev \
    gir1.2-glib-2.0 \
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