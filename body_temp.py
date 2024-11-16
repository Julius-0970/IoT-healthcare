# body_temp.py

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
                    logger.info(f"Received user info: {user_name}")

                    # 사용자 검증
                    if user_name in valid_users:
                        await websocket.send_text("User authenticated successfully.")
                        logger.info(f"User '{user_name}' authenticated successfully.")
                    else:
                        await websocket.send_text("Invalid user.")
                        logger.warning(f"User '{user_name}' authentication failed.")
                        # 인증 실패 시 연결 종료
                        await websocket.close(code=1008)  # Policy Violation
                        logger.info("WebSocket connection closed due to invalid user.")
                        break

                elif text == "GET":
                    if temperature_data_queue:
                        # 큐에 저장된 모든 데이터를 전송
                        data_to_send = list(temperature_data_queue)
                        await websocket.send_text(f"Current temperature data: {data_to_send}")
                        logger.info("Sent current temperature data to client.")

                        # 데이터 전송 후 큐 초기화
                        temperature_data_queue.clear()
                        logger.info("Temperature data queue has been cleared.")
                    else:
                        await websocket.send_text("No temperature data available.")
                        logger.info("No temperature data available to send.")
                else:
                    logger.warning(f"Received unexpected text message: {text}")
                    await websocket.send_text("Unexpected message format.")
            
            elif message["type"] == "websocket.receive.bytes":
                data = message["bytes"]
                
                if user_name and user_name in valid_users:
                    # 데이터가 유효한 사용자로부터 온 경우에만 처리
                    # 예시로, 바이너리 데이터를 UTF-8로 디코딩하여 문자열로 변환
                    try:
                        temperature_str = data.decode('utf-8')
                        temperature = float(temperature_str)  # 체온 데이터를 실수로 변환
                        temperature_data_queue.append(temperature)
                        logger.info(f"Received temperature data from '{user_name}': {temperature}")
                        
                        # 클라이언트에게 데이터 수신 확인 메시지 전송
                        await websocket.send_text("Temperature data received successfully.")
                    except (UnicodeDecodeError, ValueError) as e:
                        logger.error(f"Failed to decode temperature data: {e}")
                        await websocket.send_text("Invalid temperature data format.")
                else:
                    logger.warning("Received temperature data from unauthenticated user.")
                    await websocket.send_text("User not authenticated. Please authenticate first.")
            
            else:
                logger.warning(f"Received unknown message type: {message['type']}")
                await websocket.send_text("Unknown message type received.")
    
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected.")
    except Exception as e:
        logger.error(f"ERROR: {e}")
        # 클라이언트에게 에러 내용 전송
        await websocket.send_text(f"An error occurred: {e}")

# 저장된 body_temp 값을 조회하는 엔드포인트 (GET)
@temp_router.get("/body_temp")  
async def get_body_temp():
    if not temperature_data_queue:  # 데이터가 비어있는 경우
        return {"message": "No Body Temperature data available."}  # 데이터가 없을 경우 메시지 반환
    return {"message": "Body Temperature 서버 연결 완!", "Body Temperature Data": list(temperature_data_queue)}  # 데이터가 있을 경우 메시지와 Body Temperature 데이터 반환
