# 헬스케어 장치 정보 및 사용자 정보를 받아서 넘겨주는 코드

from fastapi import FastAPI, APIRouter
from pydantic import BaseModel
import requests

router = APIRouter()

# 데이터 형식
class DeviceData(BaseModel):
    device_id: str
    device_ip: str
    patient_id: str

#Back-server url 입력 코드(임시)
#backend_server_url = "http://{백엔드 서버 IP 주소}"

@router.post("/log")
async def receive_ack(data: DeviceData):
    try:
        response = requests.post(backend_server_url, json=data.dict())

        if response.status_code == 200:
            return {"message": "데이터 전송 성공이다 이자시가"}
        else:
            return {"message" : "너 오늘 밤샘 확정"}

    # 예외처리 코드(서버 작동 중지 방지)_오류 내용 출력
    except Exception as e:
        return {"message": f"오류 내용 : {str(e)}"}
