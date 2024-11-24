import httpx
import json  # JSON 확인을 위한 모듈 추가
from logger import get_logger  # 별도의 로깅 설정 가져오기

logger = get_logger("data_sender")

# 서버 URL 매핑 테이블
SENSOR_URL_MAPPING = {
    "ecg": "https://reptile-promoted-publicly.ngrok-free.app/ws/ecg",
    "gsr": "https://example.com/api/gsr",
    "spo2": "https://example.com/api/spo2",
    "airflow": "https://example.com/api/airflow",
    "temp": "https://example.com/api/temp",
}

async def send_data_to_backend(username, sensor_type, data_queue):
    """
    센서 데이터를 백엔드로 전송하는 함수.
    
    :param username: 사용자 이름
    :param sensor_type: 센서 종류 (예: 'ecg', 'gsr', 'spo2' 등)
    :param data_queue: 전송할 데이터 큐
    """
    if not username:
        logger.warning("사용자 이름이 설정되지 않았습니다.")
        return
        # username = "test" #return

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
        "userId": username,
        f"{sensor_type}data": list(data_queue)
    }
    # Payload 생성 로그
    # userId만 로그에 출력
    #logger.debug(f"userId: {payload['userId']}")
    logger.debug(f"Payload 생성됨: {json.dumps(payload, indent=2)}")

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
