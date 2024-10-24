from fastapi import FastAPI
import uvicorn
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles

#router로 main이 각 실행파일을 가져오도록 import
from app import router
#from patient_dispatch import router

app = FastAPI() # fastapi의 인스턴스를 app이라는 변수에 할당. (쉽게 말하면 fastapi를 다룰 수 있는 리모컨을 app이라는 애한테 줘버린 것.)
app.include_router(router)  # API 루트 경로 설정
app.mount("/", StaticFiles(directory="public", html = True), name="static") # HTML 파일에 접근(접근 경로는 GIT 내부 디렉토리)_정적파일 접근
