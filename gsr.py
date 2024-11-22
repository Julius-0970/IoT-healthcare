from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from collections import deque  # deque를 사용하기 위한 import
import logging  # 로깅 기능을 사용하기 위한 import

# FastAPI 애플리케이션과 연결하는 router 명 지정
gsr_router = APIRouter()

# 로깅 설정
logger = logging.getLogger("gsr_logger")  # 현재 모듈의 로거 인스턴스 생성
logger.setLevel(logging.DEBUG)  # 로그 레벨 설정
handler = logging.StreamHandler()
formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

# GSR 데이터를 실시간으로 송수신하기 위한 큐(데크) 생성
gsr_data_queue = deque(maxlen=416)  # 최대 416개의 최신 데이터만 저장

# GSR 데이터를 WebSocket으로 수신하는 엔드포인트
@gsr_router.websocket("/ws/gsr")
async def websocket_gsr(websocket: WebSocket):
    """
    GSR 데이터를 WebSocket으로 수신하고 처리하는 엔드포인트.
    """
    await websocket.accept()  # WebSocket 연결 수락
    logger.info("WebSocket 연결 수락됨.")

    try:
        while True:
            try:
                # 바이너리 데이터 수신
                data = await websocket.receive_bytes()
                logger.debug(f"수신된 데이터: {data.hex()}")

                # 데이터 길이 확인
                if len(data) != 86:
                    logger.warning(f"잘못된 데이터 크기 수신: {len(data)} bytes. 예상 크기: 86 bytes.")
                    await websocket.send_text("Invalid packet size. Expected 86 bytes.")
                    continue

                # 패킷 검증
                if data[0] == 0xF7 and data[-1] == 0xFA:
                    cmd_id = data[1]  # CMD 확인
                    data_size = data[2]  # DATA SIZE 확인
                    logger.debug(f"CMD ID: {cmd_id}, DATA SIZE: {data_size}")

                    # CMD와 데이터 크기를 통해 데이터 처리
                    if cmd_id == 0xA3 and data_size == 8:  # 예시 CMD ID와 데이터 크기
                        gsr_value = int.from_bytes(data[3:7], byteorder="big")
                        logger.info(f"GSR 값: {gsr_value}")

                        # 큐에 데이터 저장
                        gsr_data_queue.append(gsr_value)
                        await websocket.send_text("GSR data received successfully.")
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
                logger.error(f"데이터 처리 중 오류 발생: {e}")
                await websocket.send_text("Internal server error.")
    except WebSocketDisconnect:
        logger.info("WebSocket 연결 해제됨.")
    except Exception as e:
        logger.error(f"WebSocket 처리 중 오류 발생: {e}")

# GSR 데이터를 조회하기 위한 HTTP GET 엔드포인트
@gsr_router.get("/gsr")
async def get_gsr():
    """
    큐에 저장된 GSR 데이터를 반환하는 HTTP GET 엔드포인트.
    """
    if not gsr_data_queue:  # 데이터가 비어있는 경우
        return {"message": "No GSR data available.", "data": []}
    return {"message": "GSR 데이터 조회 성공", "data": list(gsr_data_queue)}
