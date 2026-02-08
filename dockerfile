FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y \
    gcc g++ make libffi-dev libssl-dev \
    mediainfo cron curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x entrypoint.sh

VOLUME ["/config", "/logs"]
EXPOSE 5056
ENTRYPOINT ["./entrypoint.sh"]
