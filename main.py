from fastapi import FastAPI, Response
import time
import uvicorn
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from app import router

app = FastAPI()
app.mount("/", StaticFiles(directory="public", html = True), name="static")
app.include_router(router)
