from fastapi import APIRouter
from pydantic import BaseModel

temp_router = APIRouter()

# 데이터 모델 정의
class TemperatureData(BaseModel):
    body_temp: int

# body_temp 값을 받는 엔드포인트
@temp_router.post("/body_temp")
async def receive_body_temp(data: TemperatureData):
    # 받은 body_temp 값 처리
    return {"message": "Body temperature received successfully", "body_temp": data.body_temp}

