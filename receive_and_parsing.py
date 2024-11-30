# FastAPI의 기능을 사용하기 위해 import
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
# - APIRouter: 라우터를 생성, main.py에서 관리하기 위함.
# - WebSocket: Iot장비와의 실시간 통신을 하기 위함.
# - WebSocketDisconnect: WebSocket 연결이 끊어졌을 때 발생하는 예외 처리

# user_queue 지정을 deque로 지정
# 속도 처리가 일반큐보다 빠름, 대신 데큐의 특징의 활용은 하지않음(maxlen 지정됨)
from collections import deque
# - deque: 새로운 값이 들어오면, 알아서 갱신하는 구조의 큐
#   목적: 속도가 일반큐보다 빨라서 채용, maxlen을 지정해서 데큐의 갱신은 사용 안함.

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
#   목적: 라우터에서 유저명(username), 센서 타입(sensor_type)별 엔드포인트를 동적으로 생성하데 쓰임.

# 사용자별 데이터를 저장하는 데 사용되는 defaultdict 가져오기
from collections import defaultdict
# - defaultdict: Python 딕셔너리의 확장 버전으로, 키가 없을 경우 자동으로 기본값을 생성
#   목적: 사용자 별로 데이터를 저장할 큐를 생성하기 위함. 충돌 방지 목적.

# HTTP 요청을 처리하는 requests 라이브러리 가져오기
import requests
# - requests: Python의 HTTP 요청 처리 라이브러리.
#   목적: 백엔드로의 POST 요청을 처리하기 위함.


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
    'temp': {"cmd": 0xa2, "data_size": 0x04, "queue_size": 60}, #temp는 장비의 문제로 인해, 오래 연결이 안됨. 큐의 길이의 경우 50~60으로 받아오는 게 적합함.
    'nibp': {"cmd": 0x42, "data_size": 0x04, "queue_size": 1},
    'spo2': {"cmd": 0x52, "data_size": 0x04, "queue_size": 10},
}

# 사용자별 센서 큐 저장
user_queues = defaultdict(lambda: {})

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
        config = SENSOR_CONFIGS[sensor_type] # 그냥 센서 타입. 이름만 다름.
        cmd = config["cmd"] # cmd 비교를 위해 존재
        data_size = config["data_size"] #data_size 검증

        # 패킷의 sop, cmd, data size, eop 데이터 검증
        # 이미 패킷 형식에서 위치가 고정되어 있는 값들임.
        sop = raw_data_bytes[0]  # 패킷 시작값 (SOP)
        received_cmd = raw_data_bytes[1]  # 명령어 값 (CMD)
        received_data_size = raw_data_bytes[2]  # 데이터 크기
        eop = raw_data_bytes[-1]  # 패킷 끝값 (EOP)

        # SOP와 EOP 값 검증
        if sop != 0xF7 or eop != 0xFA:
            logger.error(f"[{sensor_type}] 패킷 헤더/트레일러 불일치")
            return []

        # CMD 값 검증: 데이터가 센서 타입에 맞는 명령인지 확인
        # 가끔 ecg를 보내고, airflow를 전송하려할때 전에 전송하던 airflow값의 일부가 전송되는 경우가 종종있어서 처리함.
        if received_cmd != cmd:
            logger.warning(f"[{sensor_type}] 잘못된 cmd 값 수신: {received_cmd} (예상 cmd: {cmd})")
            return []

        # 패킷 길이에 따른 데이터 처리
        # 길이 10인 경우 : NIBP, temp, Spo2 
        # 전부 일정한 한개의 값이 필요한 경우_list에서 [-1]을 추출하는 로직은 send_to_data_backend에 존재
        if packet_length == 10:
            # SPO2 데이터 처리
            if received_cmd == 0x52:
                data_values = []
                spo2 = raw_data_bytes[5]
                data_values.append(spo2)
                return data_values

            # NIBP 데이터 처리
            elif received_cmd == 0x42:
                data_values = []
                diastolic = raw_data_bytes[4]  # 이완기 혈압
                systolic = raw_data_bytes[5]  # 수축기 혈압
                data_values.append(systolic)
                data_values.append(diastolic)
                return data_values

            elif received_cmd == 0xa2:  # TEMP 데이터 처리
                data_values = []
                high_byte = int.from_bytes(raw_data_bytes[3:5], byteorder="big")
                low_byte = int.from_bytes(raw_data_bytes[5:7], byteorder="big")
                temp_raw = (high_byte + low_byte + 4) /100.0 # temp 형식을 float로 처리.
                data_values.append(temp_raw)
                return data_values

            # 패킷 10인 단일 값만 필요한 경우에도 list처리화해서 전송 로직으로 전달.

            else:
                logger.warning(f"[{sensor_type}] 10바이트 패킷이지만 알 수 없는 cmd 값: {received_cmd}")
                return []

        # 패킷 길이에 따른 데이터 처리
        # 길이 86인 경우 : ECG, EOG, EMG, GSR, Airflow 
        # list 형태 그대로 json처리해서 넘겨짐. maxlen 15000이면 30초간의 데이터가 전송됨.
        elif packet_length == 86:
            if received_cmd == 0x12:  # ECG 데이터
                logger.info(f"[{sensor_type}] ECG 데이터 파싱 로직 실행")
                data = raw_data_bytes[3:-1]  # 데이터 본문 추출(sop, cmd, data_size, eop)를 제외한 순수 데이터 부분.
                data_values = []
                for i in range(0, len(data), 4):  # 4바이트씩 데이터 처리
                    if i + 4 > len(data):
                        break
                    byte1 = data[i] # @@ ex) 0x00
                    byte2 = data[i + 1] # @@ ex) 0x11
                    fixed_value = int.from_bytes(data[i + 2:i + 4], byteorder="big") # @@@@ ex) 0x2000
                    real_value = byte1 + byte2 + fixed_value # @@ + @@ + @@@@ ex) 0x00 + 0x11 + 0x2000 = x
                    data_values.append(real_value) # x값을 리스트에 쌓음.
                return data_values
                    
            elif received_cmd == 0x22:  # EMG 데이터 (ECG와 동일)
                logger.info(f"[{sensor_type}] EMG 데이터 파싱 로직 실행")
                data = raw_data_bytes[3:-1]
                data_values = []
                for i in range(0, len(data), 4):
                    if i + 4 > len(data):
                        break
                    byte1 = data[i]
                    byte2 = data[i + 1]
                    fixed_value = int.from_bytes(data[i + 2:i + 4], byteorder="big")
                    real_value = byte1 + byte2 + fixed_value
                    data_values.append(real_value)
                return data_values

            elif received_cmd == 0x32:  # EOG 데이터 (ECG와 동일)
                logger.info(f"[{sensor_type}] EOG 데이터 파싱 로직 실행")
                data = raw_data_bytes[3:-1]
                data_values = []
                for i in range(0, len(data), 4):
                    if i + 4 > len(data):
                        break
                    byte1 = data[i]
                    byte2 = data[i + 1]
                    fixed_value = int.from_bytes(data[i + 2:i + 4], byteorder="big")
                    real_value = byte1 + byte2 + fixed_value
                    data_values.append(real_value)
                return data_values

            elif received_cmd == 0x82:  # GSR 데이터 (ECG와 동일)
                logger.info(f"[{sensor_type}] GSR 데이터 파싱 로직 실행")
                data = raw_data_bytes[3:-1]
                data_values = []
                for i in range(0, len(data), 4):
                    if i + 4 > len(data):
                        break
                    byte1 = data[i]
                    byte2 = data[i + 1]
                    fixed_value = int.from_bytes(data[i + 2:i + 4], byteorder="big")
                    real_value = byte1 + byte2 + fixed_value
                    data_values.append(real_value)
                return data_values

            elif received_cmd == 0x62:  # Airflow 데이터
                logger.info(f"[{sensor_type}] AIRFLOW 데이터 파싱 로직 실행")
                data = raw_data_bytes[3:-1]
                data_values = []
                for i in range(0, len(data), 4):
                    if i + 4 > len(data):
                        break
                    byte1 = int.from_bytes(data[i:i + 2], byteorder="big")  # 00FF
                    byte2 = int.from_bytes(data[i + 2:i + 4], byteorder="big")  # FF00
                    real_value = byte1 + byte2
                    # 값이 0xFFFF일 경우 -1로 치환 (2의 보수 처리)
                    if real_value == 65535:
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

    try:
        # 장치 ID 및 사용자 정보 수신
        device_id = await websocket.receive_text()
        logger.info(f"장치 ID 수신: {device_id}")

        # 클라이언트로부터 username 수신
        username = await websocket.receive_text()
        logger.info(f"수신된 사용자 이름: {username}")

        # 사용자별 센서 큐 생성(각 사용자별로 작업공간 분리)_실질적인 사용자별 큐의 생성
        if username not in user_queues:
            user_queues[username] = {
                sensor: deque(maxlen=SENSOR_CONFIGS[sensor]["queue_size"])
                for sensor in SENSOR_CONFIGS.keys()
            }
        user_queue = user_queues[username][sensor_type]

        while True:
            try:
                # 패킷(데이터) 수신
                data = await websocket.receive_bytes()
                raw_data_hex = data.hex()
                logger.debug(f"수신된 데이터: {raw_data_hex}")

                # 데이터 파싱 호출 및 백엔드 서버 전송 로직
                parsed_values = parse_sensor_data(sensor_type, raw_data_hex)
                if parsed_values:
                    user_queue.extend(parsed_values) # 파싱된 데이터를 사용자 큐에 추가
                    logger.info(f"[{sensor_type}] {len(parsed_values)}개의 데이터가 저장되었습니다.")
                    await websocket.send_text(f"파싱 성공: {len(parsed_values)} {sensor_type.upper()} 데이터")

                # 큐가 가득 찼을 경우, 백엔드로 데이터 전송
                if len(user_queue) == user_queue.maxlen:
                    logger.info(f"[{sensor_type}] 큐가 최대 용량에 도달했습니다. 백엔드로 데이터 전송 시도.")
                    # 백엔드로 파싱된 데이터를 보내토록 함수를 호출하는 로직
                    backend_response = await send_to_data_backend(device_id, username, sensor_type, list(user_queue))

                    # WebSocket 응답 처리

                    # 200메세지 반환시
                    if backend_response.get("status_code") == 200:
                        logger.info(f"[{sensor_type}] 데이터 전송 성공")
                        # 라즈베리파이에게 전송 성공 메세지를 반환.
                        await websocket.send_json({
                            "status": "success",
                            "message": f"{sensor_type.upper()} 데이터 전송 성공",
                            "server_response": backend_response.get("server_response")
                        })
                    # error code가 반환시
                    else:
                        logger.error(f"[{sensor_type}] 데이터 전송 실패 - 상태 코드: {backend_response.get('status_code')}")
                        # 라즈베리파이에게 전송 실패 메세지를 반환. 
                        # 여기서 유효하지 않은 ID라고 메세지가 오는 경우에는 클라이언트에서 ID오류를 반환하게 만들 수 있음.
                        await websocket.send_json({
                            "status": "failure",
                            "message": f"{sensor_type.upper()} 데이터 전송 실패",
                            "error_code": backend_response.get("status_code", "N/A"),
                            "server_response": backend_response.get("server_response", "N/A")
                        })
                    # 클라이언트와의 통신을 끊음.
                    await websocket.close(code=1000, reason="Queue reached maximum capacity")
            except WebSocketDisconnect:
                logger.warning(f"[{sensor_type}] WebSocket 연결 끊김 (사용자: {username}).")
                break
            except Exception as e:
                logger.error(f"[{sensor_type}] WebSocket 처리 중 오류 발생: {e}")
                break
    finally:
        # 큐 삭제 및 자원 정리
        user_queues[username][sensor_type].clear()
        logger.info(f"[{sensor_type}] 큐 초기화 완료 (사용자: {username}).")


# HTTP GET 엔드포인트
# 실제 사용자들이 ws 경로로 잘 데이터가 들어왔는 지 확인하는 용도, 사용자 큐가 초기화되면 의미 없어지는 부분.
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
    # Websokcet 경로를 등록
    # partial을 사용하여 `handle_websocket` 함수에 센서 타입(`sensor_type`)을 고정 인자로 전달.
    receive_and_parsing_router.websocket(f"/ws/{username}/{sensor_type}")(partial(handle_websocket, sensor_type))
    # HTTP GET 경로를 등록
    # partial을 사용하여 `get_sensor_data` 함수에 센서 타입(`sensor_type`)을 고정 인자로 전달.
    receive_and_parsing_router.get(f"/{username}/{sensor_type}")(partial(get_sensor_data, sensor_type))
