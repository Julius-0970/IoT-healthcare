from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class SensorData(BaseModel):
    airflow: float
    temp: float
    nibp: float
    spo2: float
    eog: float
    ecg: float
    emg: float
    gsr: float

# 센서 데이터를 저장할 딕셔너리
sensor_data = {
    "airflow": None,
    "temp": None,
    "nibp": None,
    "spo2": None,
    "eog": None,
    "ecg": None,
    "emg": None,
    "gsr": None,
}

@router.post("/update_sensor_data/")
def update_sensor_data(data: SensorData):
    # 수신한 데이터로 sensor_data 업데이트
    sensor_data.update(data.dict())
    return {"Message": "센서 데이터 업데이트 완료!", "Updated Data": sensor_data}

app.include_router(router, prefix="/api")  # 필요한 경우 API 경로를 설정
