#GSR

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from collections import deque  # deque를 사용하기 위한 import
import logging  # 로깅 기능을 사용하기 위한 import

# FastAPI 애플리케이션과 연결하는 router 명 지정
gsr_router = APIRouter()

# 로깅 설정
logger = logging.getLogger("gsr_logger")  # 현재 모듈의 로거 인스턴스 생성

# GSR 데이터를 실시간으로 송수신하기 위한 큐(데크) 생성
# 최대 416개의 최신 데이터만 저장하며, 초과 시 가장 오래된 데이터가 삭제됨
gsr_data_queue = deque(maxlen=416)

# GSR 데이터를 WebSocket으로 수신하는 엔드포인트

# WebSocket 경로 설정
@gsr_router.websocket("/ws/gsr")
async def websocket_gsr(websocket: WebSocket):

    # 클라이언트의 WebSocket 연결 수락 및 대기
    await websocket.accept()  
    
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

             # 클라이언트에 수신 데이터 전송
                await websocket.send_text(f"Received GSR data - {data.hex()}")
            except ValueError:
                # 잘못된 데이터 형식 처리
                logger.warning(f"Invalid data format received: {message}")
                await websocket.send_text("Error: Invalid data format.")

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"ERROR: {e}")
        # 클라이언트에게 오류 내용 전송
        await websocket.send_text(f"An error occurred: {e}")


# GSR 데이터를 조회하기 위한 HTTP GET 엔드포인트
@gsr_router.get("/gsr")  
async def get_gsr():
    if not gsr_data_queue:  # 데이터가 비어있는 경우
        return {"message": "No GSR data available."}  # 데이터가 없을 경우 메시지 반환
    return {"message": "GSR 서버 연결 완!", "GSR_DATA": list(gsr_data_queue)}  # 데이터가 있을 경우 메시지와 GSR 데이터 반환

