import httpx
import json  # JSON 확인을 위한 모듈 추가
from logger import get_logger  # 별도의 로깅 설정 가져오기
from user_state import current_username, lock  # 상태 변수와 Lock 가져오기

global current_username 

logger = get_logger("data_sender")


# 서버 URL 매핑 테이블
SENSOR_URL_MAPPING = {
    "ecg": "https://example.com/api/ecg",
    "gsr": "https://example.com/api/gsr",
    "spo2": "https://example.com/api/spo2",
    "airflow": "https://example.com/api/airflow",
    "temp": "https://example.com/api/temp",
}

def validate_json(payload):
    """
    JSON 형식을 확인하는 함수.
    :param payload: 검증할 JSON 데이터
    :return: JSON 형식이 올바르면 True, 그렇지 않으면 False
    """
    try:
        json_str = json.dumps(payload)  # JSON 직렬화 시도
        logger.debug(f"전송할 JSON 데이터: {json_str}")
        return True
    except (TypeError, ValueError) as e:
        logger.error(f"JSON 검증 실패: {e}")
        return False

async def send_data_to_backend(sensor_type, data_queue):
    """
    센서 데이터를 백엔드로 전송하는 함수.
    
    :param sensor_type: 센서 종류 (예: 'ecg', 'gsr', 'spo2' 등)
    :param data_queue: 전송할 데이터 큐
    """
    # current_username 가져오기
    with lock:  # Lock을 사용하여 스레드 안전하게 접근
        username = current_username
        if not username:
            logger.warning("사용자 이름이 설정되지 않았습니다.")
            return

    if not data_queue:
        logger.warning(f"{sensor_type} 데이터 큐가 비어 있습니다.")
        return

    # 센서 종류에 따른 서버 URL 선택
    backend_url = SENSOR_URL_MAPPING.get(sensor_type)
    if not backend_url:
        logger.error(f"센서 종류 '{sensor_type}'에 해당하는 URL이 없습니다.")
        return

    # Payload 생성
    payload = {
        "username": username,
        f"{sensor_type}_data": list(data_queue)
    }

    # JSON 형식 검증
    if not validate_json(payload):
        logger.error(f"올바르지 않은 JSON 데이터: {payload}")
        return

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(backend_url, json=payload)
            if response.status_code == 200:
                logger.info(f"{sensor_type} 데이터 전송 성공")
                data_queue.clear()
            else:
                logger.error(f"{sensor_type} 데이터 전송 실패: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"{sensor_type} 데이터 전송 중 오류 발생: {e}")
