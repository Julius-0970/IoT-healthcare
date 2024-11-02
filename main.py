from fastapi import FastAPI
import uvicorn
# from pydantic import BaseModel
# from fastapi.staticfiles import StaticFiles

#router로 main이 각 실행파일을 가져오도록 import
from route import router
from body_temp import temp_router
from ecg import ecg_router
#from patient_dispatch import router

app = FastAPI() # fastapi의 인스턴스를 app이라는 변수에 할당. (쉽게 말하면 fastapi를 다룰 수 있는 리모컨을 app이라는 애한테 줘버린 것.)

app.include_router(router)  # route.py API 루트 경로 설정
app.include_router(temp_router) # body_temp API 루트 경로 설정
app.include_router(ecg_router)

# 루트 경로에 기본 응답을 추가
@app.get("/")
async def read_root():
    return {"message": "Welcome to the main API!"}

# 정적 파일 경로 설정 - websocket과 충돌의 여지가 있으므로, 출력은 log에 두고 정적 파일 및 경로 없음.
# app.mount("/static", StaticFiles(directory="public"), name="static")
