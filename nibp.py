# NIBP

from fastapi import APIRouter, FastAPI
from pydantic import BaseModel
import logging 

# 로그 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nibp_logger")

nibp_router = APIRouter()

# NIBP 데이터 형식을 정의하기 위한 모델 생성
class NIBPData(BaseModel):
    systolic: int   # 수축기 혈압
    diastolic: int  # 이완기 혈압

# 전역 변수 초기화
nibp_data = None  # NIBP 데이터를 저장할 전역 변수

# 저장된 NIBP 값을 조회하는 엔드포인트 (GET)
@nibp_router.get("/nibp")
async def get_nibp():
    if nibp_data is None:
        return {"message": "No NIBP data available."}  # 데이터가 없을 경우 메시지 반환
    return {"message": "NIBP data retrieved successfully", "NIBP": nibp_data}

# NIBP 값을 받는 엔드포인트 (POST)
@nibp_router.post("/nibp")
async def post_nibp(data: NIBPData):
    global nibp_data  # 전역 변수 사용
    # 받은 NIBP 값을 저장
    nibp_data = {"systolic": data.systolic, "diastolic": data.diastolic}
    return {"message": "NIBP received successfully", "NIBP": nibp_data}
