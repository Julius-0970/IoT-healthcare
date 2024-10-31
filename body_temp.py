from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from collections import deque
import logging 

#로그 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


temp_router = APIRouter()

# 큐를 사용하여 body_temp 데이터를 저장
temperature_data_queue = deque(maxlen=416)  # 최대 크기 설정

"""
# body_temp 값을 받는 엔드포인트 (POST)
@temp_router.post("/body_temp")
async def post_body_temp(data: TemperatureData):
    # 받은 body_temp 값을 큐에 저장
    temperature_data_queue.append(data.body_temp)
    return {"message": "Body temperature received successfully", "body_temp": data.body_temp}
"""
# 저장된 body_temp 값을 조회하는 엔드포인트 (GET)
@temp_router.get("/body_temp")
async def get_body_temp():
    # 저장된 모든 온도 데이터를 반환
    return {"message": "데이터 값이..", "temperature_data": list(temperature_data_queue)}


# WebSocket을 통한 온도 데이터 수신
@temp_router.websocket("/ws/body_temp")
async def body_temp_websocket(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # 클라이언트로부터 메시지를 기다림 - int변환은 백엔드에서 진행.
            temp_data = await websocket.receive_text()
            # 큐에 저장
            temperature_data_queue.append(temp_data)
            # 로그에 수신된 데이터 출력
            logger.info(f"Received temperature data: {temp_data}")  # 데이터 출력
            # 보내기전 대기상태
            await websocket.send_text(temp_data)
    except WebSocketDisconnect :
        logger.info("WebSocket disconnected")
    except Exception as e :
        logger.error(f"ERROR: {e}")
        
