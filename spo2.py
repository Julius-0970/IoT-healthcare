from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from collections import deque
from logger import get_logger  # 별도의 로깅 설정 가져오기
# import struct  # 리틀 엔디안 데이터 처리를 위한 모듈
from send_data_back import send_data_to_backend # 백엔드로의 전송로직

# FastAPI 애플리케이션과 연결하는 router 명 지정
spo2_router = APIRouter()

# 로거 생성
logger = get_logger("spo2_logger")


# spO2 데이터를 실시간으로 송수신하기 위한 큐(데크) 생성
spo2_data_queue = deque(maxlen=10)  # 최대 10개의 최신 데이터만 저장


def parse_spo2_packet(raw_data_hex):
    """
    리틀 엔디안으로 인코딩된 SpO2 패킷을 해석하여 데이터를 반환.
    - SOP: packet[0]
    - CMD: packet[1]
    - DATA_SIZE: packet[2]
    - DATA: packet[3:3+DATA_SIZE]
    - EOP: packet[-1]
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
    if cmd != 0x52:
        raise ValueError(f"잘못된 CMD: {cmd:#04x}")
    if data_size != 0x04:
        raise ValueError(f"잘못된 DATA_SIZE: {data_size} (예상: 0x04)")
    if eop != 0xFA:
        raise ValueError(f"잘못된 EOP: {eop:#04x}")

    logger.debug(f"CMD: {cmd}, DATA SIZE: {data_size}")

    spo2 = raw_data_bytes[5]

    # 데이터 처리 결과 반환
    return {
        #"BPM": bpm,    # 추출된 BPM 값
        "SpO2": spo2,  # 추출된 SpO2 값
    }

# spO2 데이터를 WebSocket으로 수신하는 엔드포인트
@spo2_router.websocket("/ws/spo2")
async def websocket_spo2(websocket: WebSocket):
    """
    spO2 데이터를 WebSocket으로 수신하고 처리하는 엔드포인트.
    """
    await websocket.accept()
    logger.info("WebSocket 연결 수락됨.")
    # 전송 성공 시 큐 초기화
    spo2_data_queue.clear()
    logger.info("SPO2 데이터 큐가 초기화되었습니다.")

    try:
        # 클라이언트로부터 device_id 수신
        device_id = await websocket.receive_text()
        logger.info(f"수신된 장비 mac 정보: {device_id}")
        
        # 클라이언트로부터 username 수신
        username = await websocket.receive_text()
        logger.info(f"수신된 사용자 이름: {username}")
        
        while True:
            try:
                # 바이너리 데이터 수신
                data = await websocket.receive_bytes()
                raw_data_hex = data.hex()
                logger.debug(f"수신된 데이터: {raw_data_hex}")

                # 패킷 해석
                try:
                    parsed_data = parse_spo2_packet(raw_data_hex)
                    logger.info(f"패킷 해석 성공: {parsed_data}")

                    # 데이터를 큐에 저장
                    spo2_data_queue.append(parsed_data)
                    logger.info("수신된 데이터가 큐에 저장되었습니다.")
                    await websocket.send_text("spO2 data received successfully.")
                    
                    # 큐가 가득 찼을 때 데이터 전송
                    if len(temperature_data_queue) == temperature_data_queue.maxlen:
                        logger.info("큐가 최대 용량에 도달했습니다. 데이터를 서버로 전송합니다.")
                        # 데이터 전송
                        await send_data_to_backend(device_id, username, "temp", spo2_data_queue[-1])
                        
                        # 전송 성공 시 큐 초기화
                        spo2_data_queue.clear()
                        logger.info("SPO2 데이터 큐가 초기화되었습니다.")
                except ValueError as ve:
                    logger.warning(f"패킷 해석 실패: {ve}")
                    await websocket.send_text("Invalid spO2 packet format.")
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
