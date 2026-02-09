FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y cron curl mediainfo && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir --upgrade pip

WORKDIR /app

# Install Python packages directly
RUN pip install --no-cache-dir \
    fastapi==0.109.0 \
    uvicorn[standard]==0.27.0 \
    httpx==0.26.0 \
    pyyaml==6.0.1 \
    scikit-learn==1.4.0 \
    numpy==1.26.3 \
    openai==1.10.0 \
    APScheduler==3.10.4 \
    requests==2.31.0 \
    pydantic==2.5.0 \
    python-multipart==0.0.6

# Copy application
COPY . .
RUN chmod +x entrypoint.sh

VOLUME ["/config", "/logs"]
EXPOSE 5056
ENTRYPOINT ["./entrypoint.sh"]
