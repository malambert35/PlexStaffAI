FROM python:3.11-slim

RUN apt-get update && apt-get install -y cron curl mediainfo && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir --upgrade pip httpx==0.27.0

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi==0.104.1 \
    uvicorn[standard]==0.24.0 \
    requests==2.31.0 \
    "openai<1.29.0" \
    pydantic==2.5.0 \
    python-multipart==0.0.6

COPY . .
RUN chmod +x entrypoint.sh

VOLUME ["/config", "/logs"]
EXPOSE 5056
ENTRYPOINT ["./entrypoint.sh"]
