# FastApi 활용을 위한 import
from fastapi import FastAPI

# FastAPI 애플리케이션 실행을 위한 ASGI 서버 구현체
import uvicorn 

 # 다른 도메인(Origin) 간의 요청을 허용하는 CORS 설정을 하기 위한 import
from starlette.middleware.cors import CORSMiddleware

# from fastapi.staticfiles import StaticFiles

# 별도의 로깅 설정 가져오기
from logger import get_logger

#router로 main이 각 실행파일을 가져오도록 import
from receive_and_parsing import receive_and_parsing_router

app = FastAPI() # fastapi의 인스턴스를 app이라는 변수에 할당. (쉽게 말하면 fastapi를 다룰 수 있는 리모컨을 app이라는 애한테 줘버린 것.)

# CORS 설정_클라이언트에서 데이터 전송시에 막지 않으려는 작업.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 출처를 허용하려면 "*" 사용
    allow_credentials=True,
    allow_methods=["*"],  # 모든 HTTP 메소드를 허용
    allow_headers=["*"],  # 모든 헤더를 허용
)
app.include_router(receive_and_parsing_router) # 데이터를 읽어와서 파싱하는 API 루트 경로 설정


# 루트 경로에 기본 응답을 추가
@app.get("/")
async def read_root():
    return {"message": "Welcome to the main API!"}

# 정적 파일 경로 설정 - websocket과 충돌의 여지가 있으므로, 출력은 log에 두고 정적 파일 및 경로 없음.
# app.mount("/static", StaticFiles(directory="public"), name="static")

"""
from body_temp import temp_router
from ecg import ecg_router
from eog import eog_router
from emg import emg_router
from gsr import gsr_router
from airflow import airflow_router
from nibp import nibp_router
from spo2 import spo2_router
"""

"""
app.include_router(temp_router) # body_temp API 루트 경로 설정
app.include_router(ecg_router) # ECG API 루트 경로 설정
app.include_router(eog_router) # EOG API 루트 경로 설정
app.include_router(emg_router) # EMG API 루트 경로 설정
app.include_router(gsr_router) # GSR API 루트 경로 설정
app.include_router(airflow_router) # airflow API 루트 경로 설정
app.include_router(nibp_router) # NIBP API 루트 경로 설정
app.include_router(spo2_router) # spO2 API 루트 경로 설정
"""
