from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from collections import deque  # deque를 사용하기 위한 import
import logging  # 로깅 기능을 사용하기 위한 import
from logger import get_logger  # 별도의 로깅 설정 가져오기
from send_data_back import send_data_to_backend # 백엔드로의 전송로직
import asyncio

# FastAPI 애플리케이션과 연결하는 router 명 지정
ecg_router = APIRouter()

# 로깅 설정
logger = get_logger("ecg_logger")
# ECG 데이터를 실시간으로 송수신하기 위한 큐(데크) 생성
ecg_data_queue = deque(maxlen=15000)  # 최대 15000개의 파싱된 데이터만 저장

# ECG 데이터를 파싱하는 함수
def parse_ecg_data(raw_data_hex):
    """
    수신된 원시 ECG 데이터(hex 문자열)를 파싱하여 실제 값 리스트로 변환합니다.
    """
    try:
        raw_data_bytes = bytes.fromhex(raw_data_hex)
        packet_length = len(raw_data_bytes)

        # 패킷 길이 확인
        if packet_length != 86:
            logger.error(f"잘못된 패킷 길이: {packet_length} bytes (예상: 86 bytes)")
            return []

        # 패킷 헤더 및 트레일러 검증
        sop = raw_data_bytes[0]
        cmd = raw_data_bytes[1]
        data_size = raw_data_bytes[2]
        eop = raw_data_bytes[-1]

        if sop != 0xF7:
            logger.error(f"잘못된 SOP: {sop:#04x}")
            return []
        if cmd != 0x12:
            logger.error(f"잘못된 CMD: {cmd:#04x}")
            return []
        if data_size != 0x50:
            logger.error(f"잘못된 DATA_SIZE: {data_size} (예상: 0x50)")
            return []
        if eop != 0xFA:
            logger.error(f"잘못된 EOP: {eop:#04x}")
            return []
        logger.debug(f"CMD: {cmd}, DATA SIZE: {data_size}")

        # 데이터 추출 및 파싱
        data = raw_data_bytes[3:-1]
        data_values = []

        for i in range(0, len(data), 4):
            if i + 4 > len(data):
                break
            byte1 = data[i]
            byte2 = data[i + 1]
            fixed_value = int.from_bytes(data[i + 2:i + 4], byteorder="big")
            real_value = byte1 + byte2 + fixed_value
            data_values.append(real_value)

        logger.info(f"파싱된 데이터 값 수: {len(data_values)}")
        return data_values

    except Exception as e:
        logger.error(f"데이터 파싱 중 오류 발생: {e}")
        return []

# ECG 데이터를 WebSocket으로 수신하는 엔드포인트
@ecg_router.websocket("/ws/ecg")
async def websocket_ecg(websocket: WebSocket):
    """
    ECG 데이터를 WebSocket으로 수신하고 처리하는 엔드포인트.
    """
    await websocket.accept()
    logger.info("WebSocket 연결 수락됨.")
    # 큐 초기화
    ecg_data_queue.clear()
    logger.info("ECG 데이터 큐가 초기화되었습니다.")

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

                # 데이터를 파싱하여 큐에 저장
                parsed_values = parse_ecg_data(raw_data_hex)
                if parsed_values:
                    ecg_data_queue.extend(parsed_values)
                    logger.info(f"{len(parsed_values)}개의 파싱된 데이터가 큐에 저장되었습니다.")
                    await websocket.send_text(f"Successfully parsed {len(parsed_values)} ECG values.")

                # 큐가 가득 찼을 때 데이터 전송
                if len(ecg_data_queue) == ecg_data_queue.maxlen:
                    logger.info("WebSocket 연결 종료: 큐가 최대 용량에 도달했습니다.")
                    await send_data_to_backend(device_id, username, "ecg", list(ecg_data_queue))
                    # WebSocket 연결 종료
                    await websocket.close(code=1000, reason="Queue reached maximum capacity")

                    # 큐 초기화
                    ecg_data_queue.clear()
                    logger.info("ECG 데이터 큐가 초기화되었습니다.")
                    return
                else:
                    logger.warning("파싱된 데이터가 없습니다.")
                    await websocket.send_text("No valid ECG data parsed.")

            except WebSocketDisconnect:
                logger.info("WebSocket 연결 해제됨.")
                break
            except Exception as e:
                logger.error(f"데이터 처리 중 오류 발생: {e}")
                await websocket.send_text("Internal server error.")
    except Exception as e:
        logger.error(f"WebSocket 처리 중 오류 발생: {e}")


# ECG 데이터를 조회하는 기존 HTTP GET 엔드포인트
@ecg_router.get("/ecg")
async def get_ecg():
    """
    큐에 저장된 파싱된 ECG 데이터를 반환하는 HTTP GET 엔드포인트.
    """
    if not ecg_data_queue:
        return {
            "status": "error",
            "message": "No ECG data available.",
            "data": []
        }
    return {
        "status": "success",
        "message": "ECG 데이터 조회 성공",
        "data": list(ecg_data_queue)
    }
