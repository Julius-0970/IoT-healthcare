from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from collections import deque
from logger import get_logger  # 별도의 로깅 설정 가져오기
from send_data_back import send_data_to_backend # 백엔드로의 전송로직

# 로거 생성
logger = get_logger("temp_logger")

# APIRouter 인스턴스 생성
temp_router = APIRouter()

# 큐를 사용하여 body_temp 데이터를 저장
temperature_data_queue = deque(maxlen=100)  # 최대 크기 설정


def parse_temp_data(raw_data_hex):
    """
    수신된 원시 ECG 데이터(hex 문자열)를 파싱하여 실제 값 리스트로 변환합니다.
    """

    raw_data_bytes = bytes.fromhex(raw_data_hex)
    packet_length = len(raw_data_bytes)

    if packet_length != 10:
        raise ValueError(f"잘못된 패킷 길이: {packet_length} bytes (예상: 10 bytes)")

    # 패킷 헤더 및 트레일러 검증
    sop = raw_data_bytes[0]
    cmd = raw_data_bytes[1]
    data_size = raw_data_bytes[2]
    eop = raw_data_bytes[-1]

    if sop != 0xF7:
        raise ValueError(f"잘못된 SOP: {sop:#04x}")
    if cmd != 0xa2:
        raise ValueError(f"잘못된 CMD: {cmd:#04x}")
    if data_size != 0x04:
        raise ValueError(f"잘못된 DATA_SIZE: {data_size} (예상: 0x04)")
    if eop != 0xFA:
        raise ValueError(f"잘못된 EOP: {eop:#04x}")

    logger.debug(f"CMD: {cmd}, DATA SIZE: {data_size}")

    # 온도 데이터 파싱
    high_byte = int.from_bytes(raw_data_bytes[3:5], byteorder="big")
    low_byte = int.from_bytes(raw_data_bytes[5:7], byteorder="big")
    temperature_raw = high_byte + low_byte
    return temperature_raw / 100.0


@temp_router.websocket("/ws/body_temp")
async def temp_websocket_handler(websocket: WebSocket):
    """
    WebSocket을 통해 체온 데이터를 수신하고 처리하는 핸들러.
    """
    await websocket.accept()
    logger.info("WebSocket 연결 수락됨.")
    # 큐 초기화
    temperature_data_queue.clear()
    logger.info("TEMP 데이터 큐가 초기화되었습니다.")

    try:
        # 클라이언트로부터 device_id 수신
        device_id = await websocket.receive_text()
        logger.info(f"수신된 장비 mac 정보: {device_id}")
        
        # 클라이언트로부터 username 수신
        username = await websocket.receive_text()
        logger.info(f"수신된 사용자 이름: {username}")

        while True:
            try:
                data = await websocket.receive_bytes()
                raw_data_hex = data.hex()
                logger.debug(f"수신된 데이터: {raw_data_hex}")

                # 데이터 파싱
                temperature = parse_temp_data(raw_data_hex)
                temperature_data_queue.append(temperature)
                logger.info(f"큐에 데이터 저장됨: {temperature}")
                await websocket.send_text("Temperature data received successfully.")

                # 큐가 가득 찼을 때 데이터 전송
                if len(temperature_data_queue) == temperature_data_queue.maxlen:
                    logger.info("큐가 최대 용량에 도달했습니다. 데이터를 서버로 전송합니다.")
                    # 클라이언트와의 연결 종료
                    await websocket.close(code=1000, reason="Queue reached maximum capacity")
                    # 데이터 전송
                    await send_data_to_backend(device_id, username, "temp", temperature_data_queue[-1])
                    
                    # 전송 성공 시 큐 초기화
                    temperature_data_queue.clear()
                    logger.info("TEMP 데이터 큐가 초기화되었습니다.")
            except ValueError as ve:
                logger.warning(f"패킷 처리 오류: {ve}")
                await websocket.send_text(str(ve))
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


@temp_router.get("/body_temp")
async def get_body_temp():
    """
    저장된 체온 데이터를 조회하는 엔드포인트.
    """
    if not temperature_data_queue:
        return {"message": "저장된 체온 데이터가 없습니다."}
    return {"message": "yes", "Temp": list(temperature_data_queue)}
