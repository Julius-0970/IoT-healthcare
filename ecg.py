# ECG
  
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from collections import deque  # deque를 사용하기 위한 import
import logging  # 로깅 기능을 사용하기 위한 import

# FastAPI 애플리케이션과 연결하는 router 명 지정
ecg_router = APIRouter()

# 로깅 설정
logging.basicConfig(level=logging.INFO)  # INFO 레벨의 로그 메시지를 출력하도록 설정
logger = logging.getLogger(__name__)  # 현재 모듈의 로거 인스턴스 생성

# ECG 데이터를 실시간으로 송수신하기 위한 큐(데크) 생성
# 최대 416개의 최신 데이터만 저장하며, 초과 시 가장 오래된 데이터가 삭제됨
ecg_data_queue = deque(maxlen=416)

# ECG 데이터를 WebSocket으로 수신하는 엔드포인트

# WebSocket 경로 설정
@ecg_router.websocket("/ws/ecg")
async def websocket_ecg(websocket: WebSocket):

    # 클라이언트의 WebSocket 연결 수락 및 대기
    await websocket.accept()  
    try:
        while True:
            # 클라이언트로부터 ECG 데이터 수신
            ecg_data = await websocket.receive_text()
            # 수신된 데이터를 큐에 추가
            ecg_data_queue.append(ecg_data)
            # 수신된 데이터 로그에 출력
            logger.info(f"Received ECG data: {ecg_data}")
            # 백엔드 서버에 수신된 데이터 전송
            await websocket.send_text(ecg_data)
    except WebSocketDisconnect:  # WebSocket 연결이 끊어졌을 때
        logger.info("ECG WebSocket disconnected")  # 로그에 연결 끊김 정보 출력
    except Exception as e:  # 다른 예외가 발생했을 때
        logger.error(f"ERROR in ECG WebSocket: {e}")  # 에러 로그 출력

# ECG 데이터를 조회하기 위한 HTTP GET 엔드포인트
ㄴ@ecg_router.get("/ecg")
async def get_ecg():
    return {
        "message": "ECG 서버 연결 완!",  # 성공 메시지
        "ECG_DATA": list(ecg_data_queue)  # 현재 저장된 ECG 데이터 리스트 반환
    }
