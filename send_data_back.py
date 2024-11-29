import httpx
import json
import requests
from logger import get_logger

logger = get_logger("data_sender")

# 서버 URL 매핑 테이블
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

    :param device_id: 장비 고유 정보 (식별자)
    :param username: 사용자 이름
    :param sensor_type: 센서 종류 (예: 'ecg', 'temp', 'spo2' 등)
    :param data: 전송할 데이터 (단일 값 또는 리스트)
    """
    if not username:
        logger.warning("사용자 이름이 설정되지 않았습니다.")
        return

    if data is None or (isinstance(data, list) and not data):
        logger.warning(f"{sensor_type} 데이터가 비어 있습니다.")
        return

    backend_url = SENSOR_URL_MAPPING.get(sensor_type)
    if not backend_url:
        logger.error(f"센서 종류 '{sensor_type}'에 해당하는 URL이 없습니다.")
        return

    logger.debug(f"선택된 서버 URL: {backend_url}")

    # 센서별 데이터 처리
    if isinstance(data, list):
        # 데이터가 리스트일 경우, 마지막 값만 선택 (단, 파형 데이터는 전체 전송)
        payload_data = data if sensor_type not in ["temp", "spo2"] else data[-1]
    else:
        # 단일 값일 경우 그대로 전송
        payload_data = data

    # 공통 Payload 생성
    payload = {
        "device_id": device_id,
        "userid": username,
        f"{sensor_type}data": payload_data  # 센서 타입에 따라 키 생성
    }

    # Payload 생성 로그
    #logger.debug(f"생성된 Payload: {payload}")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(backend_url, json=payload)

            logger.info(f"서버 상태 코드: {response.status_code}")
            logger.info(f"서버 응답 본문: {response.text}")

            if response.status_code == 200:
                try:
                    response_json = response.json()
                    logger.info(f"서버 응답 JSON: {response_json}")
                except Exception as json_error:
                    logger.warning(f"JSON 디코딩 실패, 응답 본문 그대로 사용: {response.text}")
                    response_json = {"raw_response": response.text}

                logger.info(f"{sensor_type} 데이터 전송 성공")
                return {
                    "status": "success",
                    "message": "데이터 전송 성공",
                    "server_response": response_json,
                }
            else:
                logger.error(f"{sensor_type} 데이터 전송 실패: {response.status_code}, 응답: {response.text}")
                return {
                    "status": "failure",
                    "message": "데이터 전송 실패",
                    "error_code": response.status_code,
                    "server_response": response.text,
                }
                
    except httpx.HTTPStatusError as http_error:
        logger.error(f"HTTP 상태 오류: {http_error}")
        return {
            "status": "error",
            "message": "HTTP 상태 오류 발생",
            "error_details": str(http_error),
        }
    except httpx.RequestError as request_error:
        logger.error(f"요청 오류: {request_error}")
        return {
            "status": "error",
            "message": "서버 요청 중 오류 발생",
            "error_details": str(request_error),
        }
    except Exception as e:
        logger.error(f"{sensor_type} 데이터 전송 중 예기치 못한 오류 발생: {e}")
        return {
            "status": "error",
            "message": "데이터 전송 중 연결 실패",
            "error_details": str(e),
        }
