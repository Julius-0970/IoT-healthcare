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
nibp_data = {
    "systolic": None,   # 수축기 혈압
    "diastolic": None,  # 이완기 혈압
    "pulse": None         # 심박수
}

# 저장된 NIBP 값을 조회하는 엔드포인트 (GET)
@nibp_router.get("/nibp")
async def get_nibp():
    """
    NIBP 데이터를 반환하는 HTTP GET 엔드포인트.
    """
    if all(value is None for value in nibp_data.values()):
        return {"message": "No NIBP 데이터 없음."}  # 데이터가 없을 경우 메시지 반환
    return {"message": "NIBP 데이터 조회 성공", "NIBP": nibp_data}

# WebSocket 경로 설정
@nibp_router.websocket("/ws/nibp")
async def websocket_nibp(websocket: WebSocket):
    """
    NIBP 데이터를 WebSocket으로 수신하고 처리하는 엔드포인트.

    - 데이터는 6바이트 패킷으로 수신됩니다.
    - 데이터 구조는 다음과 같다고 가정합니다:
        1. 2바이트: 심박수 (BPM)
        2. 2바이트: 수축기 혈압 (Systolic)
        3. 2바이트: 이완기 혈압 (Diastolic)
    - 데이터는 리틀 엔디안으로 인코딩되어 있음.
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

                # 데이터 해석
                if len(data) == 10:
                    # 리틀 엔디안 형식으로 값 추출
                    diastolic = data[5]  # 6번째 바이트 (diastolic)
                    systolic = data[6]   # 7번째 바이트 (systolic)
                    pulse = data[7]      # 8번째 바이트 (pulse)
                    
                    # NIBP 데이터 저장
                    nibp_data["systolic"] = systolic
                    nibp_data["diastolic"] = diastolic
                    nibp_data["pulse"] = pulse

                    logger.info(f"NIBP 데이터 업데이트: 수축기={systolic}, 이완기={diastolic}, Pulse/min={pulse}")

                    # 클라이언트에 수신 확인 메시지 전송
                    await websocket.send_text(f"NIBP data received: Systolic={systolic}, Diastolic={diastolic}, Pulse/min={pulse}")
                else:
                    logger.warning("잘못된 데이터 패킷 길이. 10바이트 필요.")
                    await websocket.send_text("Invalid data length. Expected 10 bytes.")
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
