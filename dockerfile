FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt --no-cache-dir

# Copie app/ ET static/
COPY app/ ./app/
COPY static/ ./static/
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

EXPOSE 5056
VOLUME ["/app/data"]
ENTRYPOINT ["./entrypoint.sh"]
