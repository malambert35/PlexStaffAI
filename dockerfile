FROM python:3.11-slim

# Install system deps
RUN apt-get update && apt-get install -y \
    mediainfo cron curl gcc g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy & install Python deps (pré-build wheels)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .
RUN chmod +x entrypoint.sh

VOLUME ["/config", "/logs"]
EXPOSE 5056
ENTRYPOINT ["./entrypoint.sh"]
