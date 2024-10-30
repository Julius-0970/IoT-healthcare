from fastapi import APIRouter
from pydantic import BaseModel
from collections import deque

# 데이터 모델 정의
class TemperatureData(BaseModel):
    body_temp: int

temp_router = APIRouter()

# 큐를 사용하여 body_temp 데이터를 저장
temperature_data_queue = deque(maxlen=416)  # 최대 크기 설정

# body_temp 값을 받는 엔드포인트 (POST)
@temp_router.post("/body_temp")
async def post_body_temp(data: TemperatureData):
    # 받은 body_temp 값을 큐에 저장
    temperature_data_queue.append(data.body_temp)
    return {"message": "Body temperature received successfully", "body_temp": data.body_temp}

# 저장된 body_temp 값을 조회하는 엔드포인트 (GET)
@temp_router.get("/body_temp")
async def get_body_temp():
    # 저장된 모든 온도 데이터를 반환
    return {"message": "데이터 값이..", "temperature_data": list(temperature_data_queue)}


# WebSocket을 통한 온도 데이터 수신
@temp_router.websocket("/ws/body_temp")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # 클라이언트로부터 메시지를 기다림
            data = await websocket.receive_text()
            # 수신한 데이터를 TemperatureData 모델로 변환
            temp_data = TemperatureData(body_temp=int(data))
            # 큐에 저장
            temperature_data_queue.append(temp_data.body_temp)
            await websocket.send_text(f"Received: {temp_data.body_temp}")
    except WebSocketDisconnect:
        print("WebSocket disconnected")
