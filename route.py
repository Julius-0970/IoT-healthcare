from fastapi import APIRouter
from data import SensorData # data.py의 SensoData class 참조
# /api 경로로 묶어서, 한번에 경로 관리를 진행, main.py에 보내서 파일을 나눠서 저장 및 관리가 편함
router = APIRouter()


# 센서 데이터 접근 경로 /api/sensor_data
@router.post("/sensor_data")
 #async를 씀으로 비동기 관련 작업(네트워크 요청, 파일 읽기/쓰기)에 효율적(대기시간 감소 및 자원 활용도 상승) I/O 작업 강추! 동시 작업 가능!
async def receive_sensor_data(sensorData: SensorData):  # SensorData값은 센서모델 클래스.
    return {"message": "센서 데이터가 성공적으로 수신 되었다...", "data": sensorData} 
