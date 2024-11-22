# NIBP

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import logging

# 로그 설정
logger = logging.getLogger("nibp_logger")

# APIRouter 생성
nibp_router = APIRouter()

# NIBP 데이터 초기화
nibp_data = None

# 저장된 NIBP 값을 조회하는 엔드포인트 (GET)
@nibp_router.get("/nibp")
async def get_nibp():
    if nibp_data is None:
        return {"message": "No NIBP 데이터 없음."}  # 데이터가 없을 경우 메시지 반환
    return {"message": "NIBP data retrieved successfully", "NIBP": nibp_data}
    
# WebSocket 경로 설정
@nibp_router.websocket("/ws/nibp")
async def websocket_nibp(websocket: WebSocket):
    # 클라이언트의 WebSocket 연결 수락
    await websocket.accept()
    try:
        while True:
            # 데이터 분리 (수축기, 이완기)
            try:
                #바이너리 데이터 수신
                data = await websocket.receive_bytes()
                logger.debug(f"수신된 데이터: {data.hex()}")

                # 데이터 길이 확인
                if len(data) != 10:
                    logger.warning(f"잘못된 데이터 크기 수신: {len(data)} bytes. 예상 크기: 10 bytes.")
                    await websocket.send_text("Invalid packet size. Expected 10 bytes.")
                    continue
                    
                    # 패킷 검증
                    if data[0] == 0xF7 and data[-1] == 0xFA:
                        cmd_id = data[1]  # CMD 확인
                        data_size = data[2]  # DATA SIZE 확인
                        logger.debug(f"CMD ID: {cmd_id}, DATA SIZE: {data_size}")
                
                # 클라이언트에 수신 데이터 전송
                await websocket.send_text(f"Received NIBP data - {data.hex()}")
            except ValueError:
                # 잘못된 데이터 형식 처리
                logger.warning(f"Invalid data format received: {message}")
                await websocket.send_text("Error: Invalid data format. Expected 'systolic,diastolic'")

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"ERROR: {e}")
        # 클라이언트에게 오류 내용 전송
        await websocket.send_text(f"An error occurred: {e}")
