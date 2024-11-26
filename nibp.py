from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from collections import deque  # deque를 사용하기 위한 import
from logger import get_logger  # 별도의 로깅 설정 가져오기
from send_data_back import send_data_to_backend # 백엔드로의 전송로직

# 로거 생성
logger = get_logger("nibp_logger")

# APIRouter 생성
nibp_router = APIRouter()

nibp_data_queue = deque(maxlen=2)  # 최대 15000개의 파싱된 데이터만 저장

def parse_nibp_data(raw_data_hex):
    """
    10바이트 NIBP 데이터를 파싱하는 함수.
    :param data: 수신된 10바이트 바이너리 데이터
    :return: 파싱된 NIBP 데이터
    """
    raw_data_bytes = bytes.fromhex(raw_data_hex)
    packet_length = len(raw_data_bytes)
    
    if packet_length != 10:
        raise ValueError(f"잘못된 패킷 길이: {packet_length} bytes (예상: 10 bytes)")

    # 패킷 헤더 및 트레일러 검증
    sop = raw_data_bytes[0]
    cmd = raw_data_bytes[1]
    data_size = raw_data_bytes[2]
    eop = raw_data_bytes[-1]

    if sop != 0xF7:
        raise ValueError(f"잘못된 SOP: {sop:#04x}")
    if cmd != 0x42:
        raise ValueError(f"잘못된 CMD: {cmd:#04x}")
    if data_size != 0x04:
        raise ValueError(f"잘못된 DATA_SIZE: {data_size} (예상: 0x04)")
    if eop != 0xFA:
        raise ValueError(f"잘못된 EOP: {eop:#04x}")

    logger.debug(f"CMD: {cmd}, DATA SIZE: {data_size}")

    diastolic = raw_data_bytes[4]  # 5번째 바이트 (diastolic)
    systolic = raw_data_bytes[5]   # 6번째 바이트 (systolic)
    #pulse = data[6]      # 7번째 바이트 (pulse)

    return {
        "systolic": systolic,
        "diastolic": diastolic,
        #"pulse": pulse
}

# WebSocket 경로 설정
@nibp_router.websocket("/ws/nibp")
async def websocket_nibp(websocket: WebSocket):
    """
    NIBP 데이터를 WebSocket으로 수신하고 처리하는 엔드포인트.
    """
    await websocket.accept()
    logger.info("WebSocket 연결 수락됨.")
    # 큐 초기화
    nibp_data_queue.clear()
    logger.info("NIBP 데이터 큐가 초기화되었습니다.")

    try:
        # 클라이언트로부터 device_id 수신
        device_id = await websocket.receive_text()
        logger.info(f"수신된 장비 mac 정보: {device_id}")
        
        # 클라이언트로부터 사용자 이름 수신
        username = await websocket.receive_text()
        logger.info(f"수신된 사용자 이름: {username}")
        
        while True:
            try:
                # 바이너리 데이터 수신
                data = await websocket.receive_bytes()
                raw_data_hex = data.hex()
                logger.debug(f"수신된 데이터: {raw_data_hex}")

                # 데이터 파싱
                parsed_values = parse_nibp_data(raw_data_hex)
                systolic = parsed_values["systolic"]
                diastolic = parsed_values["diastolic"]

                # 데이터 리스트에 추가
                nibp_data_queue.append(parsed_values)
                logger.info(f"NIBP 데이터 업데이트: 수축기={systolic}, 이완기={diastolic}")

                # 클라이언트에 수신 확인 메시지 전송
                await websocket.send_text(f"NIBP data received: Systolic={systolic}, Diastolic={diastolic}")

                # 큐가 2개로 가득 찼을 경우 데이터 전송
                if len(nibp_data_queue) == nibp_data_queue.maxlen:
                    logger.info("WebSocket 연결 종료: 큐가 최대 용량에 도달했습니다.")
                    # WebSocket 연결 종료
                    await websocket.close(code=1000, reason="Queue reached maximum capacity")
                    await send_data_to_backend(device_id, username, "nibp", list(nibp_data_queue))
                    
                    # 큐 초기화
                    nibp_data_queue.clear()
                    logger.info("NIBP 데이터 큐가 초기화되었습니다.")
            except ValueError as e:
                logger.warning(f"데이터 파싱 오류: {e}")
                await websocket.send_text(str(e))
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

# 저장된 NIBP 값을 조회하는 엔드포인트 (GET)
@nibp_router.get("/nibp")
async def get_nibp():
    """
    NIBP 데이터를 반환하는 HTTP GET 엔드포인트.
    """
    if not nibp_data_queue:
        return {"message": "No NIBP 데이터 없음."}  # 데이터가 없을 경우 메시지 반환
    return {"message": "NIBP 데이터 조회 성공", "NIBP": list(nibp_data_queue)}
