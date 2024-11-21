# NIBP

from fastapi import APIRouter, FastAPI
from pydantic import BaseModel
import logging 

# 로그 설정
logger = logging.getLogger("nibp_logger")

nibp_router = APIRouter()
"""
# NIBP 데이터 형식을 정의하기 위한 모델 생성
class NIBPData(BaseModel):
    systolic: int   # 수축기 혈압
    diastolic: int  # 이완기 혈압

# 전역 변수 초기화
nibp_data = None  # NIBP 데이터를 저장할 전역 변수
"""
# 저장된 NIBP 값을 조회하는 엔드포인트 (GET)
@nibp_router.get("/nibp")
async def get_nibp():
    if nibp_data is None:
        return {"message": "No NIBP data available."}  # 데이터가 없을 경우 메시지 반환
    return {"message": "NIBP data retrieved successfully", "NIBP": nibp_data}

# WebSocket 경로 설정
@spo2_router.websocket("/ws/nibp")
async def websocket_nibp(websocket: WebSocket):

    # 클라이언트의 WebSocket 연결 수락 및 대기
    await websocket.accept()  

    try:
        while True:
            # 클라이언트로부터 메시지를 기다림
            message = await websocket.receive_text()

            # 만약 메시지가 "GET"이라면 큐의 데이터를 반환
            if message == "GET":
                if spo2_data_queue:
                    # 직접 deque를 사용하여 데이터 전송
                    await websocket.send_text(f"Current spO2 data: {spo2_data_queue}")

                    # 데이터 전송 후 큐 초기화
                    spo2_data_queue.clear()
                    logger.info("spO2 data queue has been cleared.")
                else:
                    await websocket.send_text("No spO2 data available.")
            else:
                # 라즈베리파이가 보낸 데이터 처리
                spo2_data_queue.append(message)
                logger.info(f"Received spO2 data: {message}")  # 데이터 출력
                
                # 라즈베리파이 클라이언트에게 수신 메시지 전송
                await websocket.send_text(message)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"ERROR: {e}")
        #클라이언트한테 오류내용 전송
        await websocket.send_text(f"An error occurred: {e}")
