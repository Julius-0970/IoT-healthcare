from fastapi import APIRouter
from pydantic import BaseModel


# 데이터 모델 정의
class TemperatureData(BaseModel):
    body_temp: int

temp_router = APIRouter()

temperature_data_list = []

# body_temp 값을 받는 엔드포인트 (POST)
@temp_router.post("/body_temp")
async def post_body_temp(data: TemperatureData):
    # 받은 body_temp 값을 리스트에 저장
    temperature_data_list.append(data.body_temp)
    return {"message": "Body temperature received successfully", "body_temp": data.body_temp}

# 저장된 body_temp 값을 조회하는 엔드포인트 (GET)
@temp_router.get("/body_temp")
async def get_body_temp():
    # 저장된 모든 온도 데이터를 반환
    return {"message": "데이터 값이..", "temperature_data": temperature_data_list}

