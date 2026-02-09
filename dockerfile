FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y cron curl mediainfo && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir --upgrade pip

WORKDIR /app

# Copy requirements FIRST (for Docker layer caching)
COPY requirements.txt .

# Install Python dependencies from requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Make entrypoint executable
RUN chmod +x entrypoint.sh

# Volumes
VOLUME ["/config", "/logs"]

# Expose port
EXPOSE 5056

# Entrypoint
ENTRYPOINT ["./entrypoint.sh"]
