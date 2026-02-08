FROM python:3.11-slim

# System deps
RUN apt-get update && apt-get install -y \
    cron curl mediainfo \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

WORKDIR /app

# Inline pip (no requirements.txt fail)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    fastapi==0.104.1 \
    uvicorn==0.24.0 \
    requests==2.31.0 \
    openai==1.30.1 \
    pydantic==2.5.0 \
    python-multipart==0.0.6

# Copy app + static
COPY . .
COPY static/ static/  # UI dashboard
RUN chmod +x entrypoint.sh

VOLUME ["/config", "/logs"]
EXPOSE 5056
ENTRYPOINT ["./entrypoint.sh"]
