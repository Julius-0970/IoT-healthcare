from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from collections import deque
import logging

# FastAPI 애플리케이션과 연결하는 router 명 지정
emg_router = APIRouter()

# 로깅 설정
logger = logging.getLogger("emg_logger")  # 현재 모듈의 로거 인스턴스 생성
logger.setLevel(logging.DEBUG)  # 로그 레벨 설정
handler = logging.StreamHandler()
formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

# EMG 데이터를 실시간으로 송수신하기 위한 큐(데크) 생성
emg_data_queue = deque(maxlen=416)  # 최대 416개의 최신 데이터만 저장

# EMG 데이터를 WebSocket으로 수신하는 엔드포인트
@emg_router.websocket("/ws/emg")
async def websocket_emg(websocket: WebSocket):
    """
    EMG 데이터를 WebSocket으로 수신하고 처리하는 엔드포인트.
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
                emg_data_queue.append(data.hex())
                logger.info("수신된 데이터가 큐에 저장되었습니다.")

                # 클라이언트에 수신 확인 메시지 전송
                await websocket.send_text("EMG data received successfully.")
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

# EMG 데이터를 조회하기 위한 HTTP GET 엔드포인트
@emg_router.get("/emg")
async def get_emg():
    """
    큐에 저장된 EMG 데이터를 반환하는 HTTP GET 엔드포인트.
    """
    if not emg_data_queue:  # 데이터가 비어있는 경우
        return {"message": "No EMG data available.", "data": []}
    return {"message": "EMG 데이터 조회 성공", "data": list(emg_data_queue)}
