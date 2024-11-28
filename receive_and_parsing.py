from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from collections import deque
from logger import get_logger
from send_data_back import send_data_to_backend
import asyncio
from functools import partial
from collections import defaultdict


# FastAPI 애플리케이션과 연결하는 라우터 지정
receive_and_parsing_router = APIRouter()

# 공통 로깅 설정
logger = get_logger("sensor_logger")

# 센서별 설정 (필요한 센서만 추가)
SENSOR_CONFIGS = {
    "ecg": {"cmd": 0x12, "data_size": 0x50, "queue_size": 15000},
    "emg": {"cmd": 0x22, "data_size": 0x50, "queue_size": 15000},
    "eog": {"cmd": 0x32, "data_size": 0x50, "queue_size": 15000},
    "gsr": {"cmd": 0x82, "data_size": 0x50, "queue_size": 15000},
    "airflow": {"cmd": 0x62, "data_size": 0x50, "queue_size": 15000},
    "temp": {"cmd": 0xa2, "data_size": 0x04, "queue_size": 60},
    "nibp": {"cmd": 0x42, "data_size": 0x04, "queue_size": 1},
    "spo2": {"cmd": 0x52, "data_size": 0x04, "queue_size": 10},
    # 추가 센서 설정 가능
    # 아직 temp, spo2, nibp 로직 미구현
}

# 사용자별 센서별 큐 저장
user_queues = defaultdict(lambda: {})

# 공통 파싱 함수
def parse_sensor_data(sensor_type, raw_data_hex):
    """
    센서 데이터를 파싱하는 공통 함수.
    """
    try:
        # 들어온 패킷 데이터를 바이트로 변환
        raw_data_bytes = bytes.fromhex(raw_data_hex)
        # 길이 측정
        packet_length = len(raw_data_bytes)

        # 센서 설정 가져오기
        config = SENSOR_CONFIGS[sensor_type]
        cmd = config["cmd"]
        data_size = config["data_size"]

        # 패킷 길이 확인(파형 데이터의 경우 패킷의 길이가 86)
        if packet_length != 86:
            logger.error(f"[{sensor_type}] 잘못된 패킷 길이: {packet_length} bytes (예상: 86 bytes)")
            return []

        # 패킷의 sop, cmd, data size, eop 데이터 부분을 제외한 부분들을 검증
        # 패킷의 구조: sop, cmd, data size, data, eop
        sop = raw_data_bytes[0]
        received_cmd = raw_data_bytes[1]
        received_data_size = raw_data_bytes[2]
        eop = raw_data_bytes[-1]

        # sop는 f7, eop는 fa, cmd 그리고 data size는 SENSOR_CONFIGS에 맞게 검증
        if sop != 0xF7 or received_cmd != cmd or received_data_size != data_size or eop != 0xFA:
            logger.error(f"[{sensor_type}] 패킷 헤더/트레일러 불일치")
            return []

        # 데이터 파싱
        data = raw_data_bytes[3:-1]
        data_values = []

        #data부분을 4바이트씩 잘라서 파싱(파형 데이터의 경우 분석처리)
        # data : 0040 2000 0000으로 나눠서 00+40+2000+0000으로 처리 
        for i in range(0, len(data), 4):
            if i + 4 > len(data): # 80
                break
            byte1 = data[i]
            byte2 = data[i + 1]
            fixed_value = int.from_bytes(data[i + 2:i + 4], byteorder="big") # 빅-엔디안 방식
            real_value = byte1 + byte2 + fixed_value
            data_values.append(real_value)

        logger.info(f"[{sensor_type}] 파싱된 데이터 값 수: {len(data_values)}")
        return data_values

    except Exception as e:
        logger.error(f"[{sensor_type}] 데이터 파싱 중 오류 발생: {e}")
        return []

# WebSocket 처리 함수
@receive_and_parsing_router.websocket("/ws/{username}/{sensor_type}")
async def handle_websocket(sensor_type: str, username: str, websocket: WebSocket):
    """
    공통 WebSocket 처리 함수.
    :param sensor_type: 센서 유형 (예: ecg, emg 등)
    :param username: 사용자 이름
    :param websocket: WebSocket 연결 객체
    """
    await websocket.accept()
    logger.info(f"[{sensor_type}] WebSocket 연결 수락됨 (사용자: {username}).")

    try:
        # 장치 ID 수신
        device_id = await websocket.receive_text()
        logger.info(f"[{sensor_type}] 수신된 장비 ID: {device_id}, 사용자: {username}")

        # 사용자별 센서 큐 생성
        if username not in user_queues:
            user_queues[username] = {
                sensor: deque(maxlen=SENSOR_CONFIGS[sensor]["queue_size"])
                for sensor in SENSOR_CONFIGS.keys()
            }
        user_queue = user_queues[username][sensor_type]

        while True:
            try:
                # 데이터 수신 및 파싱
                raw_data_hex = (await websocket.receive_bytes()).hex()
                parsed_values = parse_sensor_data(sensor_type, raw_data_hex)

                # 파싱된 데이터 큐에 추가
                if parsed_values:
                    user_queue.extend(parsed_values)
                    logger.info(f"[{sensor_type}] {len(parsed_values)}개의 데이터가 저장되었습니다.")
                    await websocket.send_text(f"파싱 성공: {len(parsed_values)} {sensor_type.upper()} 데이터")

                # 큐가 가득 찬 경우 백엔드로 전송
                if len(user_queue) == user_queue.maxlen:
                    backend_response = await send_data_to_backend(device_id, username, sensor_type, list(user_queue))
                    logger.info(f"백엔드 응답: {backend_response}")
                    
                    if backend_response["status"] == "success":
                        await websocket.send_json(f"{sensor_type.upper()} 데이터 전송 성공", "data": backend_response})
                    else:
                        await websocket.send_json(f"{sensor_type.upper()} 데이터 전송 실패", "data": backend_response})
                    # 큐 초기화
                    user_queue.clear()
            except WebSocketDisconnect:
                logger.info(f"[{sensor_type}] WebSocket 연결 해제됨 (사용자: {username}).")
                break
            except Exception as e:
                logger.error(f"[{sensor_type}] 데이터 처리 중 오류 발생: {e}")
                await websocket.send_text("Internal server error.")
    finally:
        # 사용자 큐 삭제
        if username in user_queues:
            del user_queues[username]
            logger.info(f"사용자 {username}의 큐 삭제됨.")

# HTTP GET 엔드포인트 처리 함수
@receive_and_parsing_router.get("/data/{username}/{sensor_type}")
async def get_sensor_data(sensor_type: str, username: str):
    """
    공통 HTTP GET 처리 함수.
    :param sensor_type: 센서 유형
    :param username: 사용자 이름
    :return: 센서 데이터 큐 상태
    """
    if username not in user_queues or sensor_type not in user_queues[username]:
        return {"status": "error", "message": f"{sensor_type.upper()} 데이터 없음.", "data": []}
    return {
        "status": "success",
        "message": f"{sensor_type.upper()} 데이터 조회 성공",
        "data": list(user_queues[username][sensor_type]),
    }

# 라우터 등록
for sensor_type in SENSOR_CONFIGS.keys():
    # WebSocket 경로를 등록
    receive_and_parsing_router.websocket(f"/ws/{{username}}/{sensor_type}")(partial(handle_websocket, sensor_type))
    logger.info(f"WebSocket 경로 등록: /ws/{{username}}/{sensor_type}")
    # HTTP GET 경로를 등록
    receive_and_parsing_router.get(f"/data/{{username}}/{sensor_type}")(partial(get_sensor_data, sensor_type))
    logger.info(f"HTTP GET 경로 등록: /data/{{username}}/{sensor_type}")
