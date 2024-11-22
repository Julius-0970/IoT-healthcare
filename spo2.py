from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from collections import deque  # deque를 사용하기 위한 import
import logging  # 로깅 기능을 사용하기 위한 import

# FastAPI 애플리케이션과 연결하는 router 명 지정
spo2_router = APIRouter()

# 로깅 설정
logger = logging.getLogger("spo2_logger")  # 현재 모듈의 로거 인스턴스 생성
logger.setLevel(logging.DEBUG)  # 로그 레벨 설정
handler = logging.StreamHandler()
formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

# spO2 데이터를 실시간으로 송수신하기 위한 큐(데크) 생성
spo2_data_queue = deque(maxlen=100)  # 최대 100개의 최신 데이터만 저장

# spO2 데이터를 WebSocket으로 수신하는 엔드포인트
@spo2_router.websocket("/ws/spo2")
async def websocket_spo2(websocket: WebSocket):
    """
    spO2 데이터를 WebSocket으로 수신하고 처리하는 엔드포인트.
    """
    await websocket.accept()
    logger.info("WebSocket 연결 수락됨.")

    try:
        while True:
            try:
                # 바이너리 데이터 수신
                data = await websocket.receive_bytes()
                logger.debug(f"수신된 데이터: {data.hex()}")

                # 데이터를 큐에 저장
                spo2_data_queue.append(data.hex())
                logger.info("수신된 데이터가 큐에 저장되었습니다.")

                # 클라이언트에 수신 확인 메시지 전송
                await websocket.send_text("spO2 data received successfully.")
            except WebSocketDisconnect:
                logger.info("WebSocket 연결 해제됨.")
                break
            except Exception as e:
                logger.error(f"데이터 처리 중 오류 발생: {e}")
                await websocket.send_text("Internal server error.")
    except WebSocketDisconnect:
        logger.info("WebSocket 연결 해제됨.")
    except Exception as e:
        logger.error(f"WebSocket 처리 중 오류 발생: {e}")

# spO2 데이터를 조회하기 위한 HTTP GET 엔드포인트
@spo2_router.get("/spo2")
async def get_spo2():
    """
    큐에 저장된 spO2 데이터를 반환하는 HTTP GET 엔드포인트.
    """
    if not spo2_data_queue:  # 데이터가 비어있는 경우
        return {"message": "No spO2 data available.", "data": []}
    return {"message": "spO2 데이터 조회 성공", "data": list(spo2_data_queue)}
