from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from collections import deque
import logging
import struct  # 리틀 엔디안 데이터 처리를 위한 모듈

# FastAPI 애플리케이션과 연결하는 router 명 지정
spo2_router = APIRouter()

# 로깅 설정
logger = logging.getLogger("spo2_logger")  # 현재 모듈의 로거 인스턴스 생성
logger.setLevel(logging.DEBUG)  # 로그 레벨 설정
handler = logging.StreamHandler()
formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

# spO2 데이터를 실시간으로 송수신하기 위한 큐(데크) 생성
spo2_data_queue = deque(maxlen=100)  # 최대 100개의 최신 데이터만 저장


def parse_spo2_packet(packet: bytes):
    """
    리틀 엔디안으로 인코딩된 spO2 패킷을 해석하여 데이터를 반환
    - SOP: packet[0]
    - CMD: packet[1]
    - DATA_SIZE: packet[2]
    - DATA: packet[3:3+DATA_SIZE]
    - EOP: packet[-1]
    """
    # 패킷 검증
    if len(packet) < 7 or packet[0] != 0xF7 or packet[-1] != 0xFA:
        raise ValueError("Invalid packet format")

    # 필드 추출
    sop = packet[0]
    cmd = packet[1]
    data_size = packet[2]

    # 데이터 검증
    if data_size != 4 or len(packet[3:3 + data_size]) != data_size:
        raise ValueError("Invalid DATA_SIZE")

    # 리틀 엔디안 데이터 해석
    value_1 = int.from_bytes(packet[5:7], byteorder="little")  # 6200 -> 98
    value_2 = int.from_bytes(packet[3:5], byteorder="little")  # 005a -> 90

    eop = packet[-1]

    return {
        "SOP": sop,
        "CMD": cmd,
        "DATA_SIZE": data_size,
        "VALUE_1": value_1,
        "VALUE_2": value_2,
        "EOP": eop
    }


# spO2 데이터를 WebSocket으로 수신하는 엔드포인트
@spo2_router.websocket("/ws/spo2")
async def websocket_spo2(websocket: WebSocket):
    """
    spO2 데이터를 WebSocket으로 수신하고 처리하는 엔드포인트.
    """
    await websocket.accept()
    logger.info("WebSocket 연결 수락됨.")

    try:
        while True:
            try:
                # 바이너리 데이터 수신
                data = await websocket.receive_bytes()
                logger.debug(f"수신된 데이터: {data.hex()}")

                # 패킷 해석
                try:
                    parsed_data = parse_spo2_packet(data)
                    logger.info(f"패킷 해석 성공: {parsed_data}")

                    # 데이터를 큐에 저장
                    spo2_data_queue.append(parsed_data)
                    logger.info("수신된 데이터가 큐에 저장되었습니다.")

                    # 클라이언트에 수신 확인 메시지 전송
                    await websocket.send_text(f"spO2 data parsed successfully: {parsed_data}")
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
