# NIBP

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import logging

# 로그 설정
logger = logging.getLogger("nibp_logger")

# APIRouter 생성
nibp_router = APIRouter()


# 저장된 NIBP 값을 조회하는 엔드포인트 (GET)
@nibp_router.get("/nibp")
async def get_nibp():
    if nibp_data is None:
        return {"message": "No NIBP data available."}  # 데이터가 없을 경우 메시지 반환
    return {"message": "NIBP data retrieved successfully", "NIBP": nibp_data}
    
# WebSocket 경로 설정
@nibp_router.websocket("/ws/nibp")
async def websocket_nibp(websocket: WebSocket):
    # 클라이언트의 WebSocket 연결 수락
    await websocket.accept()
    try:
        while True:
            # 클라이언트로부터 메시지를 수신
            message = await websocket.receive_text()

            # 데이터 분리 (수축기, 이완기)
            try:
                systolic, diastolic = map(int, message.split(","))
                
                # 로그 출력
                logger.info(f"Received NIBP data: Systolic={systolic}, Diastolic={diastolic}")
                
                # 클라이언트에 수신 데이터 전송
                await websocket.send_text(f"Received NIBP data - Systolic: {systolic}, Diastolic: {diastolic}")
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
