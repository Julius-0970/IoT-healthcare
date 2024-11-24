from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from collections import deque
from logger import get_logger  # 별도의 로깅 설정 가져오기
from send_data_back import send_data_to_backend  # 서버 전송 함수 가져오기
from user_state import current_username, lock  # 상태 변수와 Lock 가져오기
import asyncio

# 로거 생성
logger = get_logger("ecg_logger")

# FastAPI 애플리케이션과 연결하는 router 명 지정
ecg_router = APIRouter()

# ECG 데이터를 실시간으로 송수신하기 위한 큐(데크) 생성
ecg_data_queue = deque(maxlen=15000)  # 최대 15000개의 데이터를 저장


# ECG 데이터를 파싱하는 함수
def parse_ecg_data(raw_data_hex):
    try:
        raw_data_bytes = bytes.fromhex(raw_data_hex)
        packet_length = len(raw_data_bytes)

        if packet_length != 86:
            logger.error(f"잘못된 패킷 길이: {packet_length} bytes (예상: 86 bytes)")
            return []

        sop = raw_data_bytes[0]
        cmd = raw_data_bytes[1]
        data_size = raw_data_bytes[2]
        eop = raw_data_bytes[-1]

        if sop != 0xf7 or cmd != 0x12 or data_size != 0x50 or eop != 0xfa:
            logger.error("패킷 검증 실패")
            return []

        # 데이터 추출
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
    
    # 현재 사용자 이름 가져오기
    async with lock:  # 동시성 보호
        # user 정보 읽어오기
        user = current_username

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
                        await send_data_to_backend(user, "ecg", ecg_data_queue)

                    await websocket.send_text(f"Successfully parsed {len(parsed_values)} ECG values.")
                else:
                    logger.warning("파싱된 데이터가 없습니다.")
                    await websocket.send_text("No valid ECG data parsed.")

            except WebSocketDisconnect:
                logger.warning("WebSocket 연결이 끊겼습니다.")
                
                # 연결이 끊겼을 때 큐에 남은 데이터를 처리
                if ecg_data_queue:
                    async with lock:  # 동시성 보호
                        user = current_username
                    logger.info(f"끊긴 후 남은 데이터 {len(ecg_data_queue)}개 전송 시도")
                    await send_data_to_backend(user, "ecg", ecg_data_queue)
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
