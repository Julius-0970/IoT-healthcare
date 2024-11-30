from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from collections import deque
from logger import get_logger
from send_to_data_back import send_to_data_backend
import asyncio
from functools import partial
from collections import defaultdict
import requests

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
    'nibp': {"cmd": 0x42, "data_size": 0x04, "queue_size": 1},
    'spo2': {"cmd": 0x52, "data_size": 0x04, "queue_size": 10},
}

# 사용자별 센서 큐 저장
# 사용자별 데이터 큐를 저장하는 구조로 defaultdict를 사용
user_queues = defaultdict(lambda: {})

# 공통 파싱 함수
def parse_sensor_data(sensor_type, raw_data_hex):
    """
    센서 데이터를 파싱하는 공통 함수.

    :param sensor_type: 센서 유형 (예: ecg, emg 등)
    :param raw_data_hex: 센서로부터 수신된 데이터 (16진수 문자열)
    :return: 파싱된 데이터 리스트
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
        sop = raw_data_bytes[0]  # 패킷 시작값 (SOP)
        received_cmd = raw_data_bytes[1]  # 명령어 값 (CMD)
        received_data_size = raw_data_bytes[2]  # 데이터 크기
        eop = raw_data_bytes[-1]  # 패킷 끝값 (EOP)

        # SOP와 EOP 값 검증
        if sop != 0xF7 or eop != 0xFA:
            logger.error(f"[{sensor_type}] 패킷 헤더/트레일러 불일치")
            return []

        # CMD 값 검증: 데이터가 센서 타입에 맞는 명령인지 확인
        if received_cmd != cmd:
            logger.warning(f"[{sensor_type}] 잘못된 cmd 값 수신: {received_cmd} (예상 cmd: {cmd})")
            return []

        # 패킷 길이에 따른 데이터 처리
        if packet_length == 10:
            # 10바이트 데이터 처리 (정형 데이터: SPO2, NIBP 등)
            if received_cmd == 0x52:  # SPO2 데이터 처리
                data_values = [raw_data_bytes[5]]  # SPO2 값만 반환
                return data_values

            elif received_cmd == 0x42:  # NIBP 데이터 처리
                diastolic = raw_data_bytes[4]  # 이완기 혈압
                systolic = raw_data_bytes[5]  # 수축기 혈압
                return [systolic, diastolic]

            elif received_cmd == 0xa2:  # TEMP 데이터 처리
                high_byte = int.from_bytes(raw_data_bytes[3:5], byteorder="big")
                low_byte = int.from_bytes(raw_data_bytes[5:7], byteorder="big")
                temp_raw = (high_byte + low_byte + 4) / 100.0  # 온도 계산
                return [temp_raw]

            else:
                logger.warning(f"[{sensor_type}] 10바이트 패킷이지만 알 수 없는 cmd 값: {received_cmd}")
                return []

        elif packet_length == 86:
            # 86바이트 데이터 처리 (파형 데이터: ECG, EMG 등)
            data = raw_data_bytes[3:-1]  # 데이터 본문 추출
            data_values = []
            for i in range(0, len(data), 4):  # 4바이트씩 데이터 처리
                byte1 = data[i]
                byte2 = data[i + 1]
                fixed_value = int.from_bytes(data[i + 2:i + 4], byteorder="big")
                real_value = byte1 + byte2 + fixed_value
                data_values.append(real_value)
            return data_values

        else:
            logger.warning(f"[{sensor_type}] 예상치 못한 패킷 길이: {packet_length}")
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

    try:
        # 장치 ID 및 사용자 정보 수신
        device_id = await websocket.receive_text()
        logger.info(f"장치 ID 수신: {device_id}")

        # 사용자별 센서 큐 생성 (필요 시)
        if username not in user_queues:
            user_queues[username] = {
                sensor: deque(maxlen=SENSOR_CONFIGS[sensor]["queue_size"])
                for sensor in SENSOR_CONFIGS.keys()
            }
        user_queue = user_queues[username][sensor_type]

        while True:
            try:
                # 데이터 수신 및 파싱
                data = await websocket.receive_bytes()
                raw_data_hex = data.hex()
                logger.debug(f"수신된 데이터: {raw_data_hex}")

                # 파싱된 데이터 큐에 추가
                parsed_values = parse_sensor_data(sensor_type, raw_data_hex)
                if parsed_values:
                    user_queue.extend(parsed_values)
                    await websocket.send_text(f"파싱 성공: {len(parsed_values)}개의 데이터 처리됨")

                # 큐가 가득 찼을 경우 백엔드로 데이터 전송
                if len(user_queue) == user_queue.maxlen:
                    backend_response = await send_to_data_backend(device_id, username, sensor_type, list(user_queue))
                    user_queue.clear()  # 큐 초기화
                    logger.info(f"[{sensor_type}] 백엔드로 데이터 전송 완료")
            except WebSocketDisconnect:
                logger.info(f"WebSocket 연결 종료: 사용자={username}, 센서={sensor_type}")
                break
            except Exception as e:
                logger.error(f"WebSocket 처리 중 오류 발생: {e}")
                break
    finally:
        user_queues[username][sensor_type].clear()
        logger.info(f"[{sensor_type}] 큐 초기화 완료: 사용자={username}")

# HTTP GET 엔드포인트
@receive_and_parsing_router.get("/{username}/{sensor_type}")
async def get_sensor_data(sensor_type: str, username: str):
    """
    HTTP GET 요청을 통해 센서 데이터를 조회.

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

# 센서별 경로 등록
for sensor_type in SENSOR_CONFIGS.keys():
    receive_and_parsing_router.websocket(f"/ws/{{username}}/{sensor_type}")(partial(handle_websocket, sensor_type))
    receive_and_parsing_router.get(f"/{username}/{sensor_type}")(partial(get_sensor_data, sensor_type))
