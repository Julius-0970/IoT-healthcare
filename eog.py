#EOG

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from collections import deque  # deque를 사용하기 위한 import
import logging  # 로깅 기능을 사용하기 위한 import

# FastAPI 애플리케이션과 연결하는 router 명 지정
eog_router = APIRouter()

# 로깅 설정
logging.basicConfig(level=logging.INFO)  # INFO 레벨의 로그 메시지를 출력하도록 설정
logger = logging.getLogger("eog_logger")  # 현재 모듈의 로거 인스턴스 생성

# EOG 데이터를 실시간으로 송수신하기 위한 큐(데크) 생성
# 최대 416개의 최신 데이터만 저장하며, 초과 시 가장 오래된 데이터가 삭제됨
eog_data_queue = deque(maxlen=416)

# EOG 데이터를 WebSocket으로 수신하는 엔드포인트

# WebSocket 경로 설정
@eog_router.websocket("/ws/eog")
async def websocket_eog(websocket: WebSocket):

    # 클라이언트의 WebSocket 연결 수락 및 대기
    await websocket.accept()  
    
        try:
        while True:
            # 클라이언트로부터 메시지를 기다림
            message = await websocket.receive_text()

            # 만약 메시지가 "GET"이라면 큐의 데이터를 반환
            if message == "GET":
                if eog_data_queue:
                    # 직접 deque를 사용하여 데이터 전송
                    await websocket.send_text(f"Current EOG data: {eog_data_queue}")

                    # 데이터 전송 후 큐 초기화
                    eog_data_queue.clear()
                    logger.info("EOG data queue has been cleared.")
                else:
                    await websocket.send_text("No EOG data available.")
            else:
                # 라즈베리파이가 보낸 데이터 처리
                eog_data_queue.append(message)
                logger.info(f"Received EOG data: {message}")  # 데이터 출력
                
                # 라즈베리파이 클라이언트에게 수신 메시지 전송
                await websocket.send_text(message)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"ERROR: {e}")
        #클라이언트한테 오류내용 전송
        await websocket.send_text(f"An error occurred: {e}")

# EOG 데이터를 조회하기 위한 HTTP GET 엔드포인트
@eog_router.get("/eog")  
async def get_eog():
    if not eog_data_queue:  # 데이터가 비어있는 경우
        return {"message": "No EOG data available."}  # 데이터가 없을 경우 메시지 반환
    return {"message": "EOG 서버 연결 완!", "EOG_DATA": list(eog_data_queue)}  # 데이터가 있을 경우 메시지와 EOG 데이터 반환

