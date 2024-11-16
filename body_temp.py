from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from collections import deque
import logging 

# 로그 설정
logger = logging.getLogger("temp_logger")
logger.setLevel(logging.DEBUG)  # 로그 레벨 설정

temp_router = APIRouter()

# 큐를 사용하여 body_temp 데이터를 저장
temperature_data_queue = deque(maxlen=15000)  # 최대 크기 설정

# 유효한 사용자 목록 (실제 환경에서는 데이터베이스나 다른 인증 방법 사용 권장)
valid_users = {"user1", "user2", "user3"}

@temp_router.websocket("/ws/body_temp")
async def body_temp_websocket(websocket: WebSocket):
    """
    Body Temperature 센서 데이터를 수신하고 처리하는 WebSocket 엔드포인트.
    - 텍스트 메시지 "USER:user1"을 통해 사용자 인증을 수행.
    - 바이너리 데이터를 통해 체온 데이터를 수신.
    - "GET" 메시지를 통해 현재 큐의 데이터를 반환.
    """
    await websocket.accept()
    user_name = None  # 사용자 이름 초기화

    try:
        while True:
            message = await websocket.receive()

            if message["type"] == "websocket.receive.text":
                text = message["text"].strip()
                
                if text.startswith("USER:"):
                    # 사용자 이름 설정
                    user_name = text.split("USER:")[1]
                    logger.info(f"사용자 정보 수신: {user_name}")

                    # 사용자 검증
                    if user_name in valid_users:
                        await websocket.send_text("User authenticated successfully.")
                        logger.info(f"사용자 '{user_name}' 인증 성공.")
                    else:
                        await websocket.send_text("Invalid user.")
                        logger.warning(f"사용자 '{user_name}' 인증 실패.")
                        # 인증 실패 시 연결 종료
                        await websocket.close(code=1008)  # Policy Violation
                        logger.info("잘못된 사용자로 인해 WebSocket 연결 종료.")
                        break

                elif text == "GET":
                    if temperature_data_queue:
                        # 큐에 저장된 모든 데이터를 전송
                        data_to_send = list(temperature_data_queue)
                        await websocket.send_text(f"Current temperature data: {data_to_send}")
                        logger.info("클라이언트에게 현재 체온 데이터 전송 완료.")

                        # 데이터 전송 후 큐 초기화
                        temperature_data_queue.clear()
                        log
