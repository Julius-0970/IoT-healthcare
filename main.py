from fastapi import FastAPI, Response
import time
import uvicorn
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from app import router

app = FastAPI() # fastapi의 인스턴스를 app이라는 변수에 할당. (쉽게 말하면 fastapi를 다룰 수 있는 리모컨을 app이라는 애한테 줘버린 것.)
app.include_router(router)  # API 루트 경로 설정
app.mount("/static", StaticFiles(directory="public", html = True), name="static") # HTML 파일에 접근(접근 경로는 GIT 내부 디렉토리)_정적파일 접근
