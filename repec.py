from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from collections import deque
from logger import get_logger
from send_data_back import send_data_to_backend
import asyncio

# 공통 로깅 설정
logger = get_logger("sensor_logger")

# 센서별 설정 (필요한 센서만 추가)
SENSOR_CONFIGS = {
    "ecg": {"cmd": 0x12, "data_size": 0x50, "queue_size": 15000},
    "emg": {"cmd": 0x22, "data_size": 0x50, "queue_size": 15000},
    "eog": {"cmd": 0x32, "data_size": 0x50, "queue_size": 15000},
    "gsr": {"cmd": 0x82, "data_size": 0x50, "queue_size": 15000},
    "airflow": {"cmd": 0x62, "data_size": 0x50, "queue_size": 15000},
    # 추가 센서 설정 가능
}

# 센서별 큐 저장
sensor_queues = {sensor: deque(maxlen=config["queue_size"]) for sensor, config in SENSOR_CONFIGS.items()}

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
# url에 타입별 경로를 지정
@sensor_router.websocket("/ws/{sensor_type}")
#센서 경로에서 type을 읽어옴
async def handle_websocket(sensor_type: str, websocket: WebSocket):
    """
    공통 WebSocket 처리 함수.
    """
    await websocket.accept()
    logger.info(f"[{sensor_type}] WebSocket 연결 수락됨.")
    sensor_queue = sensor_queues[sensor_type]
    # 시작시 혹시 모를 남아있는 데이터 삭제.
    sensor_queue.clear()
    logger.info(f"[{sensor_type}] 데이터 큐가 초기화되었습니다.")

    try:
        # 클라이언트로부터 device_id와 username 수신
        device_id = await websocket.receive_text()
        username = await websocket.receive_text()
        logger.info(f"[{sensor_type}] 수신된 장비 ID: {device_id}, 사용자 이름: {username}")

        while True:
            try:
                data = await websocket.receive_bytes()
                raw_data_hex = data.hex()
                parsed_values = parse_sensor_data(sensor_type, raw_data_hex)

                # 파싱된 데이터가 존재할때 각 타입에 맞는 센서의 큐로 적재
                if parsed_values:
                    sensor_queue.extend(parsed_values)
                    logger.info(f"[{sensor_type}] {len(parsed_values)}개의 데이터가 큐에 저장되었습니다.")
                    await websocket.send_text(f"파싱 및 적재 성공 {len(parsed_values)} {sensor_type.upper()}") #대문자 표기

                # 큐가 가득 찼을 때 데이터 전송
                if len(sensor_queue) == sensor_queue.maxlen:
                    backend_response = await send_data_to_backend(device_id, username, sensor_type, list(sensor_queue))
                    if backend_response["status"] == "success":
                        await websocket.send_text(f"{sensor_type.upper()} 데이터 전송완료되었습니다.")
                    else:
                        await websocket.send_json(backend_response["server_response"])

                    # 큐 초기화 및 연결 종료
                    sensor_queue.clear()
                    logger.info(f"[{sensor_type}] 데이터 큐가 초기화되었습니다.")
                    # 웹소켓 통신 종료.
                    await websocket.close(code=1000, reason="Queue reached maximum capacity")
                    return
            except WebSocketDisconnect:
                logger.info(f"[{sensor_type}] WebSocket 연결 해제됨.")
                break
            except Exception as e:
                logger.error(f"[{sensor_type}] 데이터 처리 중 오류 발생: {e}")
                await websocket.send_text("Internal server error.")
    except Exception as e:
        logger.error(f"[{sensor_type}] WebSocket 처리 중 오류 발생: {e}")

# HTTP GET 엔드포인트 처리 함수
async def get_sensor_data(sensor_type):
    """
    공통 HTTP GET 처리 함수.
    """
    sensor_queue = sensor_queues[sensor_type]
    if not sensor_queue:
        return {"status": "error", "message": f"{sensor_type.upper()} 데이터 없음~", "data": []}
    return {"status": "success", "message": f"{sensor_type.upper()} 데이터 조회 성공", "data": list(sensor_queue)}

# 라우터 생성
sensor_router = APIRouter()

# 동적 라우트 등록(SENSOR_CONFIGS의 key값으로 임시함수를 통해 자동 경로 생성) ex) websocket: ws/ecg, GET : /ecg 
for sensor_type in SENSOR_CONFIGS.keys():
    sensor_router.websocket(f"/ws/{sensor_type}")(lambda websocket, s=sensor_type: handle_websocket(s, websocket))
    sensor_router.get(f"/{sensor_type}")(lambda s=sensor_type: get_sensor_data(s))
