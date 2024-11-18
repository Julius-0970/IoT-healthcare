from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
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
    - 클라이언트로부터 바이너리 데이터를 수신하고 처리.
    """
    await websocket.accept()
    logger.info("WebSocket 연결 수락됨.")

    try:
        while True:
            try:
                # 바이너리 데이터 수신
                data = await websocket.receive_bytes()
                logger.debug(f"수신된 데이터: {data.hex()}")

                # 데이터 길이 확인
                if len(data) != 10:
                    logger.warning(f"잘못된 데이터 크기 수신: {len(data)} bytes. 예상 크기: 10 bytes.")
                    await websocket.send_text("Invalid packet size. Expected 10 bytes.")
                    continue

                # 패킷 검증
                if data[0] == 0xF7 and data[-1] == 0xFA:
                    cmd_id = data[1]  # CMD 확인
                    data_size = data[2]  # DATA SIZE 확인
                    logger.debug(f"CMD ID: {cmd_id}, DATA SIZE: {data_size}")

                    # CMD와 데이터 크기를 통해 온도 데이터인지 확인
                    if cmd_id == 0xA2 and data_size == 4:
                        try:
                            high_byte = int.from_bytes(data[3:5], byteorder='big')  # 상위 2바이트
                            low_byte = int.from_bytes(data[5:7], byteorder='big')   # 하위 2바이트
                            logger.debug(f"High Byte: {high_byte}, Low Byte: {low_byte}")

                            temperature_raw = high_byte + low_byte
                            temperature = temperature_raw / 100.0
                            temperature_data_queue.append(temperature)
                            logger.info(f"큐에 데이터 저장됨: {temperature}")
                            await websocket.send_text("Temperature data received successfully.")
                        except IndexError as ie:
                            logger.error(f"데이터 해석 오류: {ie}")
                            await websocket.send_text("Data parsing error.")
                    else:
                        logger.warning(f"잘못된 CMD ID 또는 데이터 크기: CMD ID={cmd_id}, DATA SIZE={data_size}")
                        await websocket.send_text("Invalid CMD ID or DATA SIZE.")
                else:
                    logger.warning("패킷의 시작 또는 끝 바이트가 올바르지 않음.")
                    await websocket.send_text("Invalid packet format.")
            except WebSocketDisconnect:
                logger.info("WebSocket 연결 해제됨.")
                break
            except Exception as e:
                logger.error(f"데이터 수신 및 처리 중 오류 발생: {e}")
                await websocket.send_text("Internal server error.")
    except WebSocketDisconnect:
        logger.info("WebSocket 연결 해제됨.")
    except Exception as e:
        logger.error(f"WebSocket 처리 중 오류 발생: {e}")

# 저장된 body_temp 값을 조회하는 엔드포인트 (GET)
@temp_router.get("/body_temp")  
async def get_body_temp():
    if not temperature_data_queue:  # 데이터가 비어있는 경우
        return {"message": "저장된 체온 데이터가 없습니다."}  # 데이터가 없을 경우 메시지 반환
    # 큐에 저장된 데이터를 출력
    return {"message": "Body Temp received successfully", "Temp": list(temperature_data_queue)}
