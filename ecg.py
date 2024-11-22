from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from collections import deque  # deque를 사용하기 위한 import
import logging  # 로깅 기능을 사용하기 위한 import

# FastAPI 애플리케이션과 연결하는 router 명 지정
ecg_router = APIRouter()

# 로깅 설정
logger = logging.getLogger("ecg_logger")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

# ECG 데이터를 실시간으로 송수신하기 위한 큐(데크) 생성
ecg_data_queue = deque(maxlen=15000)  # 최대 15000개의 파싱된 데이터만 저장

# ECG 데이터를 파싱하는 함수
def parse_ecg_data(raw_data_hex):
    """
    수신된 원시 ECG 데이터(hex 문자열)를 파싱하여 실제 값 리스트로 변환합니다.
    패킷 구조:
    - SOP (1바이트): f7
    - CMD (1바이트): 12
    - DATA_SIZE (1바이트): 50 (16진수) -> 80 (10진수)
    - DATA (80바이트)
    - CHECKSUM (2바이트)
    - EOP (1바이트): fa
    """
    try:
        raw_data_bytes = bytes.fromhex(raw_data_hex)
        packet_length = len(raw_data_bytes)

        # 패킷 길이 확인
        if packet_length != 86:
            logger.error(f"잘못된 패킷 길이: {packet_length} bytes (예상: 86 bytes)")
            return []

        # 패킷 헤더 및 트레일러 추출
        sop = raw_data_bytes[0]
        cmd = raw_data_bytes[1]
        data_size = raw_data_bytes[2]
        checksum = raw_data_bytes[83:85]  # 2바이트 체크섬
        eop = raw_data_bytes[85]

        # 패킷 구조 검증
        if sop != 0xf7:
            logger.error(f"잘못된 SOP: {sop:#04x}")
            return []
        if cmd != 0x12:
            logger.error(f"잘못된 CMD: {cmd:#04x}")
            return []
        if data_size != 0x50:
            logger.error(f"잘못된 DATA_SIZE: {data_size} (예상: 0x50)")
            return []
        if eop != 0xfa:
            logger.error(f"잘못된 EOP: {eop:#04x}")
            return []

        # DATA 추출
        expected_data_length = data_size  # 80바이트
        actual_data_length = packet_length - 6  # SOP + CMD + DATA_SIZE + CHECKSUM + EOP = 6바이트
        if actual_data_length != expected_data_length:
            logger.error(f"DATA_SIZE와 실제 데이터 크기가 일치하지 않습니다. DATA_SIZE: {data_size}, 실제: {actual_data_length}")
            return []

        data = raw_data_bytes[3:83]  # DATA 부분 추출 (80바이트)

        data_values = []
        for i in range(0, len(data), 4):
            if i + 4 > len(data):
                logger.warning(f"데이터 청크가 4바이트에 미치지 않습니다: {data[i:]}")
                break

            # 4바이트씩 분할
            low_bytes = data[i:i+2]
            high_bytes = data[i+2:i+4]

            # Big Endian으로 변환
            low = int.from_bytes(low_bytes, byteorder='big')
            high = int.from_bytes(high_bytes, byteorder='big')

            # 실제 값 계산
            real_value = (high << 8) + low  # (high * 256) + low

            # 유효 값 범위 제한 제거: 모든 real_value를 저장
            data_values.append(real_value)

        logger.info(f"파싱된 데이터 값 수: {len(data_values)}")
        return data_values

    except ValueError as ve:
        logger.error(f"Hex 변환 오류: {ve}")
        return []
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

    try:
        while True:
            try:
                # 바이너리 데이터 수신
                data = await websocket.receive_bytes()
                raw_data_hex = data.hex()
                logger.debug(f"수신된 데이터: {raw_data_hex}")

                # 데이터를 파싱하여 큐에 저장
                parsed_values = parse_ecg_data(raw_data_hex)
                if parsed_values:
                    ecg_data_queue.extend(parsed_values)
                    logger.info(f"{len(parsed_values)}개의 파싱된 데이터가 큐에 저장되었습니다.")
                else:
                    logger.warning("파싱된 데이터가 없습니다.")

                # 클라이언트에 수신 확인 메시지 전송
                await websocket.send_text("ECG data received and parsed successfully.")
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

# ECG 데이터를 조회하는 기존 HTTP GET 엔드포인트
@ecg_router.get("/ecg")
async def get_ecg():
    """
    큐에 저장된 파싱된 ECG 데이터를 반환하는 HTTP GET 엔드포인트.
    """
    if not ecg_data_queue:
        return {"message": "No ECG data available.", "data": []}
    return {"message": "ECG 데이터 조회 성공", "data": list(ecg_data_queue)}
