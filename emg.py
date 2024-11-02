from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from collections import deque  # deque를 사용하기 위한 import
import logging  # 로깅 기능을 사용하기 위한 import

# FastAPI 애플리케이션과 연결하는 router 명 지정
emg_router = APIRouter()

# 로깅 설정
logging.basicConfig(level=logging.INFO)  # INFO 레벨의 로그 메시지를 출력하도록 설정
logger = logging.getLogger("emg_logger")  # 현재 모듈의 로거 인스턴스 생성

# EMG 데이터를 실시간으로 송수신하기 위한 큐(데크) 생성
# 최대 416개의 최신 데이터만 저장하며, 초과 시 가장 오래된 데이터가 삭제됨
emg_data_queue = deque(maxlen=416)

# EMG 데이터를 WebSocket으로 수신하는 엔드포인트

# WebSocket 경로 설정
@emg_router.websocket("/ws/emg")
async def websocket_emg(websocket: WebSocket):

    # 클라이언트의 WebSocket 연결 수락 및 대기
    await websocket.accept()  
    try:
        while True:
            # 클라이언트로부터 EMG 데이터 수신
            emg_data = await websocket.receive_text()
            # 수신된 데이터를 큐에 추가
            emg_data_queue.append(emg_data)
            # 수신된 데이터 로그에 출력
            logger.info(f"Received EMG data: {emg_data}")
            # 백엔드 서버에 수신된 데이터 전송
            await websocket.send_text(emg_data)
    except WebSocketDisconnect:  # WebSocket 연결이 끊어졌을 때
        logger.info("EMG WebSocket disconnected")  # 로그에 연결 끊김 정보 출력
    except Exception as e:  # 다른 예외가 발생했을 때
        logger.error(f"ERROR in EMG WebSocket: {e}")  # 에러 로그 출력

# EMG 데이터를 조회하기 위한 HTTP GET 엔드포인트
@emg_router.get("/emg")  # 변경: ecg_router -> emg_router
async def get_emg():
    return {
        "message": "EMG 서버 연결 완!",  # 성공 메시지
        "EMG_DATA": list(emg_data_queue)  # 현재 저장된 EMG 데이터 리스트 반환
    }
