from fastapi import APIRouter

# /api 경로로 묶어서, 한번에 경로 관리를 진행, main.py에 보내서 파일을 나눠서 저장 및 관리가 편함
router = APIRouter()


# 센서 데이터 접근 경로 /api/sensor_data
@router.get("/sensor_data")
async def receive_sensor_data(sensor_data: SensorData):
    return {"message": "센서 데이터가 성공적으로 수신 되었다..."}
