from fastapi import FastAPI
from openai import OpenAI
import requests, os, sqlite3, datetime

app = FastAPI()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
DB_PATH = "/config/staffai.db"

sqlite3.connect(DB_PATH).execute('CREATE TABLE IF NOT EXISTS decisions (id INTEGER PRIMARY KEY, data TEXT)')
print("PlexStaffAI ready")

@app.get("/")
def root():
    return {"status": "OK", "port": 5056}

@app.get("/test")
def test():
    return {"openai": client.models.list(limit=1).data[0].id}

@app.get("/moderate")
def moderate():
    return {"mock": "IA approve/reject works - add Overseerr keys"}
