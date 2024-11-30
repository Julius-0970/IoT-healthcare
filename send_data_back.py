import httpx
import json  # JSON 확인을 위한 모듈 추가
from logger import get_logger  # 별도의 로깅 설정 가져오기

logger = get_logger("data_sender")

# 서버 URL 매핑 테이블(파형데이터만 일단 넣음)_정형 데이터의 경우에는 리스트 처리를 안하기 때문에 예외처리 필요
SENSOR_URL_MAPPING = {
    "ecg": "https://reptile-promoted-publicly.ngrok-free.app/ws/ecg",
    "eog": "https://reptile-promoted-publicly.ngrok-free.app/ws/eog",
    "emg": "https://reptile-promoted-publicly.ngrok-free.app/ws/emg",
    "gsr": "https://reptile-promoted-publicly.ngrok-free.app/ws/gsr",
    "airflow": "https://reptile-promoted-publicly.ngrok-free.app/ws/airflow",
    "temp": "https://reptile-promoted-publicly.ngrok-free.app/ws/bodytemp",
    "nibp": "https://reptile-promoted-publicly.ngrok-free.app/ws/nibp",
    "spo2": "https://reptile-promoted-publicly.ngrok-free.app/ws/spo2"
}

async def send_data_to_backend(device_id, username, sensor_type, data):
    """
    센서 데이터를 백엔드로 전송하는 함수.
    :device_id: 장비 고유 정보(식별자)
    :param username: 사용자 이름
    :param sensor_type: 센서 종류 (예: 'ecg', 'gsr', 'spo2' 등)
    :param data: 전송할 데이터 단일 데이터 혹은 큐(리스트)
    """
    if not username:
        logger.warning("사용자 이름이 설정되지 않았습니다.")
        return

    # 데이터가 리스트인 경우와 단일 데이터인 경우에 데이터가 비어있는지 확인.
    if data is None or (isinstance(data, list) and not data):
        logger.warning(f"{sensor_type} 데이터가 비어 있습니다.")
        return

    # 센서 종류에 따른 서버 URL 선택
    backend_url = SENSOR_URL_MAPPING.get(sensor_type)
    if not backend_url:
        logger.error(f"센서 종류 '{sensor_type}'에 해당하는 URL이 없습니다.")
        return
        
    logger.debug(f"선택된 서버 URL: {backend_url}")
    # 단일 값인지, 리스트인지 확인
    if isinstance(data, list):
        payload_data = list(data)  # 리스트인 경우 복사
        if sensor_type == "nibp":
            # Payload 생성
            payload = {
                "device_id": device_id,
                "userid": username,
                "systolic": payload_data[0],
                "diastolic": payload_data[-1]
            }
        else:
            # Payload 생성
            payload = {
                "device_id": device_id,
                "userid": username,
                f"{sensor_type}data": payload_data
            }
    else:
        payload_data = data  # 단일 값인 경우 들어온 값 그대로 전송
        # Payload 생성
        payload = {
            "device_id": device_id,
            "userid": username,
            f"{sensor_type}data": payload_data
        }
    # Payload 생성 로그
    logger.debug(f"device_id: {payload['device_id']}, userid: {payload['userid']}")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(backend_url, json=payload)

            # 상태 코드와 서버 응답 메시지 로그
            logger.info(f"HTTP 상태 코드: {response.status_code}")
            logger.info(f"서버 응답 메시지: {response.text}")
            
            # 응답 반환
            return {
                "status_code": response.status_code,
                "server_response": response.text
            }

    except httpx.HTTPStatusError as http_err:
        # HTTP 상태 코드 에러 (응답 있음)
        logger.error(f"HTTP 에러 발생: {http_err.response.status_code}, 응답: {http_err.response.text}")
        return {
            "status": "failure",
            "message": "HTTP 에러 발생",
            "error_code": http_err.response.status_code,
            "server_response": http_err.response.text,
        }

    except httpx.RequestError as req_err:
        # 요청 실패 (연결 문제 등)
        logger.error(f"요청 실패: {req_err}")
        logger.error(f"HTTP 에러 발생: {http_err.response.status_code}, 응답: {http_err.response.text}")
        # 상태 코드와 서버 응답 메시지 로그
        return {
            "status": "failure",
            "message": "요청 실패",
            "error_details": str(req_err),
        }

    except Exception as e:
        # 기타 예외
        logger.error(f"예상치 못한 오류 발생: {e}")
        logger.error(f"HTTP 에러 발생: {http_err.response.status_code}, 응답: {http_err.response.text}")
        return {
            "status": "error",
            "message": "예상치 못한 오류 발생",
            "error_details": str(e),
        }
