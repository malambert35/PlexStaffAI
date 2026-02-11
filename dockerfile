FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh
EXPOSE 5056
ENTRYPOINT ["./entrypoint.sh"]
