from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import StreamingResponse
from collections import deque
import logging
import io
import matplotlib.pyplot as plt

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

        # SOP, CMD, Data Size, EOP를 제외한 데이터 추출
        # SOP(1바이트), CMD(1바이트), Data Size(2바이트), EOP(1바이트)
        if len(raw_data_bytes) < 5:
            logger.error("데이터 길이가 너무 짧습니다.")
            return []

        sop = raw_data_bytes[0]
        cmd = raw_data_bytes[1]
        data_size = int.from_bytes(raw_data_bytes[2:4], byteorder='little')
        eop = raw_data_bytes[-1]
        data_bytes = raw_data_bytes[4:-1]

        logger.debug(f"SOP: {sop}, CMD: {cmd}, Data Size: {data_size}, EOP: {eop}")

        # 데이터 길이 검증
        if len(data_bytes) != data_size:
            logger.error("데이터 크기가 일치하지 않습니다.")
            return []

        # 데이터 파싱
        # 2바이트씩 읽어서 빅 엔디안으로 해석
        for i in range(0, len(data_bytes), 2):
            if i + 1 < len(data_bytes):
                data_pair = data_bytes[i:i+2]
                value = int.from_bytes(data_pair, byteorder='big')
                data_values.append(value)
            else:
                logger.warning("남은 바이트가 충분하지 않습니다.")
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

                # 데이터를 큐에 저장
                ecg_data_queue.append(raw_data_hex)
                logger.info("수신된 데이터가 큐에 저장되었습니다.")

                # 클라이언트에 수신 확인 메시지 전송
                await websocket.send_text("ECG data received successfully.")
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

# ECG 데이터를 조회하고 그래프로 반환하는 HTTP GET 엔드포인트
@ecg_router.get("/ecg")
async def get_ecg():
    """
    큐에 저장된 ECG 데이터를 파싱하고, 그래프로 반환하는 HTTP GET 엔드포인트.
    """
    if not ecg_data_queue:
        raise HTTPException(status_code=404, detail="No ECG data available.")

    # 큐에 저장된 모든 데이터 파싱
    parsed_values = []
    for raw_data_hex in ecg_data_queue:
        values = parse_ecg_data(raw_data_hex)
        parsed_values.extend(values)

    if not parsed_values:
        raise HTTPException(status_code=500, detail="Failed to parse ECG data.")

    # 그래프 생성
    plt.figure(figsize=(10, 4))
    plt.plot(parsed_values)
    plt.title("ECG Data")
    plt.xlabel("Sample")
    plt.ylabel("Value")
    plt.grid(True)

    # 그래프를 바이너리 스트림으로 변환
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()

    return StreamingResponse(buf, media_type="image/png")
