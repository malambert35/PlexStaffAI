FROM python:3.12-slim

WORKDIR /app

# Upgrade pip + install
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip list | grep openai || (echo "❌ openai MISSING" && exit 1)

# Copie code
COPY app/ ./app/
COPY static/ ./static/
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

EXPOSE 5056
VOLUME ["/app/data"]
ENTRYPOINT ["./entrypoint.sh"]
