# FastAPI의 기능을 사용하기 위해 import
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
# - APIRouter: 라우터를 생성, main.py에서 관리하기 위함.
# - WebSocket: Iot장비와의 실시간 통신을 하기 위함.
# - WebSocketDisconnect: WebSocket 연결이 끊어졌을 때 발생하는 예외 처리
# - Request: Redis 인스턴스를 app.state에서 가져오기 위함.

# 사용자 정의 로깅 설정 가져오기
from logger import get_logger
# - get_logger: 프로젝트에서 공통적으로 사용할 로깅 설정 함수
#   목적: 테스트 환경에서 실제로 값에 대한 로그 출력을 위함.

# 데이터 전송을 위한 외부 모듈 가져오기
from send_to_data_back import send_to_data_backend
# - send_to_data_backend: 백엔드로 센서값 전송을 위한 함수 불러오기
#   목적: handle_websocket에서 send_to_data_backend를 통해 json형식으로 백엔드에 데이터를 전송하기 위함.

import asyncio
# - asyncio: Python의 비동기 프로그래밍을 지원하는 모듈.
#   목적: 비동기처리를 통해 들어오는 값들이 많을 경우의 병목을 방지하기 위함.

from functools import partial
# - partial: 함수의 일부 매개변수를 고정해 새로운 함수를 생성 임시 함수 느낌으로 처리.
#   목적: 라우터에서 유저명(username), 센서 타입(sensor_type)별 엔드포인트를 동적으로 생성하는데 쓰임.


# FastAPI 애플리케이션과 연결하는 라우터 생성
receive_and_parsing_router = APIRouter()

# 공통 로깅 설정
logger = get_logger("sensor_logger")


# 센서별 설정 정의
# cmd: 센서 타입에 따른 명령어 값
# data_size: 데이터 크기 (바이트 단위)
# queue_size: 사용자별 큐 크기
SENSOR_CONFIGS = {
    'ecg': {"cmd": 0x12, "data_size": 0x50, "queue_size": 15000},
    'emg': {"cmd": 0x22, "data_size": 0x50, "queue_size": 15000},
    'eog': {"cmd": 0x32, "data_size": 0x50, "queue_size": 15000},
    'gsr': {"cmd": 0x82, "data_size": 0x50, "queue_size": 15000},
    'airflow': {"cmd": 0x62, "data_size": 0x50, "queue_size": 15000},
    'temp': {"cmd": 0xa2, "data_size": 0x04, "queue_size": 60},
    'nibp': {"cmd": 0x42, "data_size": 0x04, "queue_size": 2},
    'spo2': {"cmd": 0x52, "data_size": 0x04, "queue_size": 10},
}

# 공통 파싱 함수(모든 센서를 여기서 파싱)
# 인자값으로 Iot장비로 부터 받아온, 센서 타입과 패킷을 인자로 받음.
def parse_sensor_data(sensor_type, raw_data_hex):
    """
    :sensor_type: 센서 유형 (예: ecg, emg 등)
    :raw_data_hex: 센서로부터 수신된 패킷 (16진수 문자열 : f7a2000000000000fa 의 형식)
    :패킷 형식에 대해서 자세히 알고 싶다면, 라즈베리파이의 DAQ_Seral.py의 정의된 부분을 보면 됨.
    :return: 파싱된 데이터 리스트를 반환, 그리고 json으로 묶어서 Post로 백엔드로 전송
    """
    try:
        # 들어온 패킷 데이터를 바이트로 변환
        raw_data_bytes = bytes.fromhex(raw_data_hex)
        # 패킷 길이 계산
        packet_length = len(raw_data_bytes)

        # 센서 설정 가져오기
        config = SENSOR_CONFIGS[sensor_type]
        cmd = config["cmd"]
        data_size = config["data_size"]

        # 패킷의 sop, cmd, data size, eop 데이터 검증
        sop = raw_data_bytes[0]
        received_cmd = raw_data_bytes[1]
        received_data_size = raw_data_bytes[2]
        eop = raw_data_bytes[-1]

        # SOP와 EOP 값 검증
        if sop != 0xF7 or eop != 0xFA:
            logger.error(f"[{sensor_type}] 패킷 헤더/트레일러 불일치")
            return []

        # CMD 값 검증
        if received_cmd != cmd:
            logger.warning(f"[{sensor_type}] 잘못된 cmd 값 수신: {received_cmd} (예상 cmd: {cmd})")
            return []

        # 패킷 길이 10 : NIBP, TEMP, SPO2
        if packet_length == 10:
            if received_cmd == 0x52:  # SPO2
                return [raw_data_bytes[5]]

            elif received_cmd == 0x42:  # NIBP
                diastolic = raw_data_bytes[4]
                systolic = raw_data_bytes[5]
                return [systolic, diastolic]

            elif received_cmd == 0xa2:  # TEMP
                high_byte = int.from_bytes(raw_data_bytes[3:5], byteorder="big")
                low_byte = int.from_bytes(raw_data_bytes[5:7], byteorder="big")
                temp_raw = ((high_byte + low_byte) / 100.0) + 5
                return [temp_raw]

            else:
                logger.warning(f"[{sensor_type}] 10바이트 패킷이지만 알 수 없는 cmd 값: {received_cmd}")
                return []

        # 패킷 길이 86 : ECG, EOG, EMG, GSR, AIRFLOW
        elif packet_length == 86:
            data = raw_data_bytes[3:-1]
            data_values = []

            if received_cmd in [0x12, 0x22, 0x32, 0x82]:  # ECG, EMG, EOG, GSR — 동일 파싱
                logger.info(f"[{sensor_type}] 데이터 파싱 로직 실행")
                for i in range(0, len(data), 4):
                    if i + 4 > len(data):
                        break
                    byte1 = data[i]
                    byte2 = data[i + 1]
                    fixed_value = int.from_bytes(data[i + 2:i + 4], byteorder="big")
                    real_value = byte1 + byte2 + fixed_value
                    data_values.append(real_value)
                return data_values

            elif received_cmd == 0x62:  # AIRFLOW
                logger.info(f"[{sensor_type}] AIRFLOW 데이터 파싱 로직 실행")
                for i in range(0, len(data), 4):
                    if i + 4 > len(data):
                        break
                    byte1 = int.from_bytes(data[i:i + 2], byteorder="big")
                    byte2 = int.from_bytes(data[i + 2:i + 4], byteorder="big")
                    real_value = byte1 + byte2
                    if real_value == 65535:  # 2의 보수 처리
                        data_values.append(-1)
                        return data_values
                    data_values.append(real_value)
                return data_values

            else:
                logger.warning(f"[{sensor_type}] 86바이트 패킷이지만 알 수 없는 cmd 값: {received_cmd}")
                return []

        else:
            logger.warning(f"[{sensor_type}] 잘못된 패킷 길이: {packet_length} (10 또는 86 예상)")
            return []

    except Exception as e:
        logger.error(f"[{sensor_type}] 데이터 파싱 중 오류 발생: {e}")
        return []


# WebSocket 처리 함수
@receive_and_parsing_router.websocket("/ws/{username}/{sensor_type}")
async def handle_websocket(sensor_type: str, username: str, websocket: WebSocket):
    """
    WebSocket을 통해 센서 데이터를 수신하고 처리하는 함수.

    :param sensor_type: 센서 유형
    :param username: 사용자 이름
    :param websocket: WebSocket 연결 객체
    """
    await websocket.accept()
    logger.info(f"WebSocket 연결 수락됨: 사용자={username}, 센서={sensor_type}")

    # Redis 인스턴스 및 키 설정
    redis = websocket.app.state.redis
    redis_key = f"{username}:{sensor_type}"
    queue_size = SENSOR_CONFIGS[sensor_type]["queue_size"]

    try:
        # 장치 ID 및 사용자 정보 수신
        device_id = await websocket.receive_text()
        logger.info(f"장치 ID 수신: {device_id}")

        username = await websocket.receive_text()
        logger.info(f"수신된 사용자 이름: {username}")

        while True:
            try:
                # 패킷(데이터) 수신
                data = await websocket.receive_bytes()
                raw_data_hex = data.hex()
                logger.debug(f"수신된 데이터: {raw_data_hex}")

                # 데이터 파싱 및 Redis 큐에 저장
                parsed_values = parse_sensor_data(sensor_type, raw_data_hex)
                if parsed_values:
                    await redis.rpush(redis_key, *[str(v) for v in parsed_values])
                    logger.info(f"[{sensor_type}] {len(parsed_values)}개의 데이터가 저장되었습니다.")

                # 큐가 가득 찼을 경우, 백엔드로 데이터 전송
                current_len = await redis.llen(redis_key)
                if current_len >= queue_size:
                    logger.info(f"[{sensor_type}] 큐가 최대 용량에 도달했습니다. 백엔드로 데이터 전송 시도.")
                    raw_data = await redis.lrange(redis_key, 0, -1)
                    data_list = [int(v) for v in raw_data]
                    await send_to_data_backend(device_id, username, sensor_type, data_list)

                    # 클라이언트와의 통신을 끊음.
                    await websocket.close(code=1000, reason="Queue reached maximum capacity")

            except WebSocketDisconnect:
                logger.warning(f"[{sensor_type}] WebSocket 연결 끊김 (사용자: {username}).")
                break
            except Exception as e:
                logger.error(f"[{sensor_type}] WebSocket 처리 중 오류 발생: {e}")
                break

    finally:
        # Redis 큐 정리
        await redis.delete(redis_key)
        logger.info(f"[{sensor_type}] Redis 큐 정리 완료 (사용자: {username}).")


# HTTP GET 엔드포인트
@receive_and_parsing_router.get("/{username}/{sensor_type}")
async def get_sensor_data(sensor_type: str, username: str, request: Request):
    """
    HTTP GET 요청을 통해 센서 데이터를 조회.

    :param sensor_type: 센서 유형
    :param username: 사용자 이름
    :param request: Redis 인스턴스 접근을 위한 Request 객체
    :return: 센서 데이터 큐 상태
    """
    redis = request.app.state.redis
    redis_key = f"{username}:{sensor_type}"
    data = await redis.lrange(redis_key, 0, -1)

    if not data:
        return {"status": "error", "message": f"{sensor_type.upper()} 데이터 없음.", "data": []}
    return {
        "status": "success",
        "message": f"{sensor_type.upper()} 데이터 조회 성공",
        "data": [int(v) for v in data],
    }


# 센서별 경로 등록
for sensor_type in SENSOR_CONFIGS.keys():
    # WebSocket 경로 등록
    receive_and_parsing_router.websocket(f"/ws/{{username}}/{sensor_type}")(partial(handle_websocket, sensor_type))
    logger.info(f"WebSocket 경로 등록: /ws/{{username}}/{sensor_type}")
    # HTTP GET 경로 등록
    receive_and_parsing_router.get(f"/{{username}}/{sensor_type}")(partial(get_sensor_data, sensor_type))
    logger.info(f"HTTP GET 경로 등록: {{username}}/{sensor_type}")
