FROM python:3.11-slim

# System dependencies used by the entrypoint and optional media inspection.
RUN apt-get update && apt-get install -y --no-install-recommends cron curl mediainfo \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --upgrade pip

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x entrypoint.sh

VOLUME ["/config", "/logs"]
EXPOSE 5056
ENTRYPOINT ["./entrypoint.sh"]
