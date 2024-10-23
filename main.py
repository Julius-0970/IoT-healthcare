from fastapi import FastAPI, Response
import time
import uvicorn
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from app import router

app = FastAPI()
app.include_router(router, prefix="/api")  # API 경로 설정
app.mount("/", StaticFiles(directory="public", html = True), name="static")
