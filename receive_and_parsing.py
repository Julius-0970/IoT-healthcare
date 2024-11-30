from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from collections import deque
from logger import get_logger
from send_to_data_back import send_to_data_backend
import asyncio
from functools import partial
from collections import defaultdict
import requests


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

        # 패킷의 sop, cmd, data size, eop 데이터 부분을 제외한 부분들을 검증
        sop = raw_data_bytes[0]
        received_cmd = raw_data_bytes[1]
        received_data_size = raw_data_bytes[2]
        eop = raw_data_bytes[-1]

        # sop는 f7, eop는 fa, cmd 그리고 data size는 SENSOR_CONFIGS에 맞게 검증
        if sop != 0xF7 or eop != 0xFA:
            logger.error(f"[{sensor_type}] 패킷 헤더/트레일러 불일치")
            return []

        # 패킷 길이에 따른 처리
        if packet_length == 10:
            if received_cmd == 0x52:  # SPO2 데이터
                logger.info(f"[{sensor_type}] SPO2 데이터 파싱 로직 실행")
                data_values = []
                spo2 = raw_data_bytes[5]
                data_values.append(spo2)
                return data_values

            elif received_cmd == 0x42:  # NIBP 데이터
                logger.info(f"[{sensor_type}] NIBP 데이터 파싱 로직 실행")
                # 수축기와 이완기 값만 반환
                data_values = []
                diastolic = int(raw_data_bytes[4])  # 5번째 바이트 (diastolic)
                systolic = int(raw_data_bytes[5])   # 6번째 바이트 (systolic)
                data_values.append(systolic)
                data_values.append(diastolic)
                return data_values

            elif received_cmd == 0xa2:  # TEMP 데이터
                logger.info(f"[{sensor_type}] TEMP 데이터 파싱 로직 실행")
                data_values = []
                high_byte = int.from_bytes(raw_data_bytes[3:5], byteorder="big")
                low_byte = int.from_bytes(raw_data_bytes[5:7], byteorder="big")
                temp_raw = (high_byte + low_byte + 4) /100.0
                data_values.append(temp_raw)
                return data_values

            else:
                logger.warning(f"[{sensor_type}] 10바이트 패킷이지만 알 수 없는 cmd 값: {received_cmd}")
                return []

        elif packet_length == 86:
            if received_cmd == 0x12:  # ECG 데이터
                logger.info(f"[{sensor_type}] ECG 데이터 파싱 로직 실행")
                data = raw_data_bytes[3:-1]
                data_values = []
                for i in range(0, len(data), 4):
                    byte1 = data[i]
                    byte2 = data[i + 1]
                    fixed_value = int.from_bytes(data[i + 2:i + 4], byteorder="big")
                    real_value = byte1 + byte2 + fixed_value
                    data_values.append(real_value)
                return data_values

            elif received_cmd == 0x22:  # EMG 데이터
                logger.info(f"[{sensor_type}] EMG 데이터 파싱 로직 실행")
                data = raw_data_bytes[3:-1]
                data_values = []
                for i in range(0, len(data), 4):
                    byte1 = data[i]
                    byte2 = data[i + 1]
                    fixed_value = int.from_bytes(data[i + 2:i + 4], byteorder="big")
                    real_value = byte1 + byte2 + fixed_value
                    data_values.append(real_value)
                return data_values

            elif received_cmd == 0x32:  # EOG 데이터
                logger.info(f"[{sensor_type}] EOG 데이터 파싱 로직 실행")
                data = raw_data_bytes[3:-1]
                data_values = []
                for i in range(0, len(data), 4):
                    byte1 = data[i]
                    byte2 = data[i + 1]
                    fixed_value = int.from_bytes(data[i + 2:i + 4], byteorder="big")
                    real_value = byte1 + byte2 + fixed_value
                    data_values.append(real_value)
                return data_values

            elif received_cmd == 0x82:  # GSR 데이터
                logger.info(f"[{sensor_type}] GSR 데이터 파싱 로직 실행")
                data = raw_data_bytes[3:-1]
                data_values = []
                for i in range(0, len(data), 4):
                    byte1 = data[i]
                    byte2 = data[i + 1]
                    fixed_value = int.from_bytes(data[i + 2:i + 4], byteorder="big")
                    real_value = byte1 + byte2 + fixed_value
                    data_values.append(real_value)
                return data_values

            elif received_cmd == 0x62:  # Airflow 데이터
                logger.info(f"[{sensor_type}] Airflow 데이터 파싱 로직 실행")
                data = raw_data_bytes[3:-1]
                data_values = []
                for i in range(0, len(data), 4):
                    byte1 = data[i]
                    byte2 = data[i + 1]
                    fixed_value = int.from_bytes(data[i + 2:i + 4], byteorder="big")
                    real_value = byte1 + byte2 + fixed_value
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
    공통 WebSocket 처리 함수.
    :param sensor_type: 센서 유형 (예: ecg, emg 등)
    :param username: 사용자 이름
    :param websocket: WebSocket 연결 객체
    """
    await websocket.accept()
    logger.info(f"[{sensor_type}] WebSocket 연결 수락됨 (사용자: {username}).")

    try:
        # 클라이언트로부터 device_id 수신
        device_id = await websocket.receive_text()
        logger.info(f"수신된 장비 mac 정보: {device_id}")

        # 클라이언트로부터 username 수신
        username = await websocket.receive_text()
        logger.info(f"수신된 사용자 이름: {username}")

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
                data = await websocket.receive_bytes()
                raw_data_hex = data.hex()
                logger.debug(f"수신된 데이터: {raw_data_hex}")

                # 사용자 및 센서 타입에 대한 큐가 존재하는지 확인, 초기화
                if username not in user_queues:
                    user_queues[username] = {}
                if sensor_type not in user_queues[username]:
                    user_queues[username][sensor_type] = []

                parsed_values = parse_sensor_data(sensor_type, raw_data_hex)
                if parsed_values:
                    user_queue.extend(parsed_values)
                    logger.info(f"[{sensor_type}] {len(parsed_values)}개의 데이터가 저장되었습니다.")
                    await websocket.send_text(f"파싱 성공: {len(parsed_values)} {sensor_type.upper()} 데이터")

                # 파싱된 데이터 큐에 다 찼을 경우, 데이터 전송
                if len(user_queue) == user_queue.maxlen:
                    backend_response = await send_to_data_backend(device_id, username, sensor_type, list(user_queue))
                    logger.info(f"백엔드 응답: {backend_response}")

                    # WebSocket 응답 처리
                    if backend_response["status"] == "success":
                        await websocket.send_json({
                            "status": "success",
                            "message": f"{sensor_type.upper()} 데이터 전송 성공",
                            "server_response": backend_response["server_response"]
                        })
                    elif backend_response["status"] == "failure":
                        await websocket.send_json({
                            "status": "failure",
                            "message": f"{sensor_type.upper()} 데이터 전송 실패",
                            "error_code": backend_response.get("error_code", "N/A"),
                            "server_response": backend_response["server_response"]
                        })
                    else:
                        await websocket.send_json({
                            "status": "error",
                            "message": f"{sensor_type.upper()} 데이터 전송 중 오류 발생",
                            "error_details": backend_response.get("error_details", "N/A")
                        })
                    # 클라이언트와의 통신을 끊음.
                    await websocket.close(code=1000, reason="Queue reached maximum capacity")
                    logger.info(f"사용자 {username}와의 연결 종료")
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
@receive_and_parsing_router.get("/{username}/{sensor_type}")
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
    receive_and_parsing_router.get(f"{{username}}/{sensor_type}")(partial(get_sensor_data, sensor_type))
    logger.info(f"HTTP GET 경로 등록: {{username}}/{sensor_type}")
