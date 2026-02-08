FROM python:3.11-slim

# System libs + compilers
RUN apt-get update && apt-get install -y \
    curl cron mediainfo \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Pip upgrade + strict install
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt && \
    pip install --no-cache-dir --find-links /wheels -r requirements.txt

COPY . .
RUN chmod +x entrypoint.sh

VOLUME ["/config", "/logs"]
EXPOSE 5056
ENTRYPOINT ["./entrypoint.sh"]
