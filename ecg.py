from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from collections import deque  # deque를 사용하기 위한 import
import logging  # 로깅 기능을 사용하기 위한 import
import asyncio
import httpx  # 다른 서버로 데이터를 전송하기 위한 HTTP 클라이언트
from user_state import current_username  # user_state.py에서 username 가져오기

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

        if sop != 0xf7 or cmd != 0x12 or data_size != 0x50 or eop != 0xfa:
            logger.error("패킷 검증 실패")
            return []

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

    try:
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

                    # 큐가 가득 찼을 때 데이터 전송
                    if len(ecg_data_queue) == ecg_data_queue.maxlen:
                        await send_ecg_data_to_backend()

                    await websocket.send_text(f"Successfully parsed {len(parsed_values)} ECG values.")
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

# ECG 데이터를 백엔드 서버로 전송하는 함수
async def send_ecg_data_to_backend():
    """
    현재 사용자 이름과 ECG 데이터를 다른 백엔드 서버로 전송합니다.
    """
    global current_username

    if not current_username:
        logger.warning("사용자 이름이 설정되지 않았습니다. 데이터 전송 불가.")
        return

    if not ecg_data_queue:
        logger.warning("ECG 데이터가 비어 있습니다. 데이터 전송 불가.")
        return

    # 백엔드 서버 URL
    backend_url = "https://reptile-promoted-publicly.ngrok-free.app/ws/ecg"

    # 전송 데이터 구성
    payload = {
        "username": current_username,
        "ecg_data": list(ecg_data_queue)
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(backend_url, json=payload)
            if response.status_code == 200:
                logger.info("ECG 데이터 전송 성공")
                ecg_data_queue.clear()  # 데이터 전송 후 큐 초기화
            else:
                logger.error(f"ECG 데이터 전송 실패: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"ECG 데이터 전송 중 오류 발생: {e}")


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
