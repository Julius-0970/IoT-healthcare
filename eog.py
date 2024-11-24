from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from collections import deque
from logger import get_logger  # 별도의 로깅 설정 가져오기

# FastAPI 애플리케이션과 연결하는 router 명 지정
eog_router = APIRouter()


# 로거 생성
logger = get_logger("eog_logger")

# EOG 데이터를 실시간으로 송수신하기 위한 큐(데크) 생성
eog_data_queue = deque(maxlen=15000)  # 최대 15000개의 최신 데이터만 저장

# EMG 데이터를 파싱하는 함수
def parse_eog_data(raw_data_hex):
    """
    수신된 원시 EMG 데이터(hex 문자열)를 파싱하여 실제 값 리스트로 변환합니다.
    패킷 구조:
    - SOP (1바이트): f7
    - CMD (1바이트): 32
    - DATA_SIZE (1바이트): 50 (16진수) -> 80 (10진수)
    - DATA (80바이트, 4바이트씩 나뉨)
    - EOP (1바이트): fa
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

        if sop != 0xf7:
            logger.error(f"잘못된 SOP: {sop:#04x}")
            return []
        if cmd != 0x32:
            logger.error(f"잘못된 CMD: {cmd:#04x}")
            return []
        if data_size != 0x50:
            logger.error(f"잘못된 DATA_SIZE: {data_size} (예상: 0x50)")
            return []
        if eop != 0xfa:
            logger.error(f"잘못된 EOP: {eop:#04x}")
            return []

        # 데이터 추출 (SOP, CMD, DATA_SIZE, CHECKSUM, EOP 제거)
        data = raw_data_bytes[3:-1]  # 3바이트(SOP, CMD, DATA_SIZE) + 1바이트(EOP) 제외
        data_values = []

        # 데이터를 4바이트씩 나누어 파싱
        for i in range(0, len(data), 4):
            if i + 4 > len(data):
                logger.warning(f"데이터 청크가 4바이트에 미치지 않습니다: {data[i:]}")
                break

            # 앞의 4자리 값
            byte1 = data[i]      # 첫 번째 바이트
            byte2 = data[i + 1]  # 두 번째 바이트

            # 고정된 4자리 값
            fixed_value = int.from_bytes(data[i + 2:i + 4], byteorder="big")

            # 앞의 4자리 값 계산: byte1 + byte2
            prefix_sum = byte1 + byte2

            # 최종 계산: prefix_sum + 고정된 4자리 값
            real_value = prefix_sum + fixed_value

            # 값 저장
            data_values.append(real_value)

        logger.info(f"파싱된 데이터 값 수: {len(data_values)}")
        return data_values

    except ValueError as ve:
        logger.error(f"Hex 변환 오류: {ve}")
        return []
    except Exception as e:
        logger.error(f"데이터 파싱 중 오류 발생: {e}")
        return []
        
# EOG 데이터를 WebSocket으로 수신하는 엔드포인트
@eog_router.websocket("/ws/eog")
async def websocket_eog(websocket: WebSocket):
    """
    EOG 데이터를 WebSocket으로 수신하고 처리하는 엔드포인트.
    """
    await websocket.accept()
    logger.info("WebSocket 연결 수락됨.")

    try:
        while True:
            try:
                # 바이너리 데이터 수신
                data = await websocket.receive_bytes()
                logger.debug(f"수신된 데이터: {data.hex()}")

                # 데이터를 큐에 저장
                eog_data_queue.append(data.hex())
                logger.info("수신된 데이터가 큐에 저장되었습니다.")

                # 클라이언트에 수신 확인 메시지 전송
                await websocket.send_text("EOG data received successfully.")
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

# EOG 데이터를 조회하기 위한 HTTP GET 엔드포인트
@eog_router.get("/eog")
async def get_eog():
    """
    큐에 저장된 EOG 데이터를 반환하는 HTTP GET 엔드포인트.
    """
    if not eog_data_queue:  # 데이터가 비어있는 경우
        return {"message": "No EOG data available.", "data": []}
    return {"message": "EOG 데이터 조회 성공", "data": list(eog_data_queue)}
