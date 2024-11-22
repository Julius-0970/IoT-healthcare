from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import logging

# 로그 설정
logger = logging.getLogger("nibp_logger")
logger.setLevel(logging.DEBUG)  # 로그 레벨 설정
handler = logging.StreamHandler()
formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

# APIRouter 생성
nibp_router = APIRouter()

# NIBP 데이터 초기화
nibp_data = None

# 저장된 NIBP 값을 조회하는 엔드포인트 (GET)
@nibp_router.get("/nibp")
async def get_nibp():
    """
    NIBP 데이터를 반환하는 HTTP GET 엔드포인트.
    """
    if nibp_data is None:
        return {"message": "No NIBP 데이터 없음."}  # 데이터가 없을 경우 메시지 반환
    return {"message": "NIBP 데이터 조회 성공", "NIBP": nibp_data}

# WebSocket 경로 설정
@nibp_router.websocket("/ws/nibp")
async def websocket_nibp(websocket: WebSocket):
    """
    NIBP 데이터를 WebSocket으로 수신하고 처리하는 엔드포인트.
    """
    global nibp_data
    await websocket.accept()
    logger.info("WebSocket 연결 수락됨.")

    try:
        while True:
            try:
                # 바이너리 데이터 수신
                data = await websocket.receive_bytes()
                logger.debug(f"수신된 데이터: {data.hex()}")

                # 데이터를 저장
                nibp_data = data.hex()
                logger.info("수신된 데이터가 저장되었습니다.")

                # 클라이언트에 수신 확인 메시지 전송
                await websocket.send_text("NIBP data received successfully.")
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
