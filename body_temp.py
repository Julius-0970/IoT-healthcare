from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from collections import deque
import logging

# 로그 설정
logger = logging.getLogger("temp_logger")
logger.setLevel(logging.DEBUG)  # 로그 레벨 설정

# APIRouter 인스턴스 생성
temp_router = APIRouter()

# 큐를 사용하여 body_temp 데이터를 저장
temperature_data_queue = deque(maxlen=15000)  # 최대 크기 설정

@temp_router.websocket("/ws/body_temp")
async def body_temp_websocket(websocket: WebSocket):
    """
    Body Temperature 센서 데이터를 수신하고 저장하는 WebSocket 엔드포인트.
    - 클라이언트로부터 10바이트 크기의 16진수 패킷을 바이너리 형태로 수신.
    - 수신된 패킷을 큐에 저장.
    """
    await websocket.accept()
    logger.info("WebSocket 연결 수락됨.")

    try:
        while True:
            message = await websocket.receive()

            if message["type"] == "websocket.receive.bytes":
                data = message["bytes"]

                # 데이터 길이 검증
                if len(data) != 10:
                    logger.warning(f"잘못된 데이터 크기 수신: {len(data)} bytes. 예상 크기: 10 bytes.")
                    await websocket.send_text("Invalid packet size. Expected 10 bytes.")
                    continue

                # 데이터 저장
                temperature_data_queue.append(data)
                logger.debug(f"체온 데이터 큐에 저장됨: {data.hex()}")

                # 클라이언트에게 데이터 수신 확인 메시지 전송
                await websocket.send_text("Temperature packet received successfully.")
            
            else:
                logger.warning(f"알 수 없는 메시지 유형 수신: {message['type']}")
                await websocket.send_text("Only binary data packets are accepted.")
    
    except WebSocketDisconnect:
        logger.info("WebSocket 연결 해제됨.")
    except Exception as e:
        logger.error(f"오류 발생: {e}")
        # 클라이언트에게 에러 내용 전송
        await websocket.send_text(f"An error occurred: {e}")

# 저장된 body_temp 값을 조회하는 엔드포인트 (GET)
@temp_router.get("/body_temp")  
async def get_body_temp():
    if not temperature_data_queue:  # 데이터가 비어있는 경우
        return {"message": "저장된 체온 데이터가 없습니다."}  # 데이터가 없을 경우 메시지 반환
    # 큐에 저장된 데이터를 16진수 문자열로 변환하여 반환
    data_hex = [data.hex() for data in temperature_data_queue]
    return {
        "message": "Body Temperature 데이터 조회 성공",
        "Body Temperature Data": data_hex
    }  # 데이터가 있을 경우 메시지와 Body Temperature 데이터 반환
