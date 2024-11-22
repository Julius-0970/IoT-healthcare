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
ecg_data_queue = deque(maxlen=15000)  # 최대 15000개의 최신 데이터만 저장

# ECG 데이터를 파싱하는 함수
def parse_ecg_data(raw_data_hex):
    """
    수신된 원시 ECG 데이터(hex 문자열)를 파싱하여 실제 값 리스트로 변환합니다.
    """
    try:
        raw_data_bytes = bytes.fromhex(raw_data_hex)
        data_values = []
        i = 0
        while i < len(raw_data_bytes) - 1:
            # 데이터 값 추출 (2바이트)
            data_pair = raw_data_bytes[i:i+2]
            data_value = int.from_bytes(data_pair, byteorder='big')
            i += 2
            # 마커 값 추출 (2바이트)
            if i < len(raw_data_bytes) - 1:
                marker_pair = raw_data_bytes[i:i+2]
                marker_value = int.from_bytes(marker_pair, byteorder='big')
                i += 2
            else:
                marker_value = None
            # 실제 값 계산
            if marker_value is not None:
                real_value = data_value - marker_value
                data_values.append(real_value)
            else:
                # 마커 값이 없을 경우 데이터 값만 추가
                data_values.append(data_value)
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
