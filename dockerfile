FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    cron curl mediainfo \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --upgrade pip

WORKDIR /app

# INLINE PIP (no requirements fail)
RUN pip install --no-cache-dir \
    fastapi==0.104.1 uvicorn==0.24.0 \
    requests==2.31.0 openai==1.30.1 \
    pydantic==2.5.0 python-multipart==0.0.6

# SINGLE COPY tout (no cache conflict)
COPY . .
RUN chmod +x entrypoint.sh && ls -la static/  # Debug list

VOLUME ["/config", "/logs"]
EXPOSE 5056
ENTRYPOINT ["./entrypoint.sh"]
