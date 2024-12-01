import httpx
import json  # JSON 확인을 위한 모듈 추가
from logger import get_logger  # 별도의 로깅 설정 가져오기

logger = get_logger("back_data_sender")

# 서버 URL 매핑 테이블(실제 데이터를 받는 url, ngrok으로 뚫어둠)
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

# 백엔드로 파싱된 패킷을 리스트에 넣어 json으로 보내고, 응답을 받는 함수
# 여기서 data는 전부다 list
async def send_to_data_backend(device_id, username, sensor_type, data):
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

    # 데이터가 유효한 리스트인지 확인
    if not data:
        logger.warning(f"{sensor_type} 데이터가 비어 있거나 유효하지 않습니다.")
        return

    # 센서 종류에 따른 서버 URL 선택
    backend_url = SENSOR_URL_MAPPING.get(sensor_type)
    if not backend_url:
        logger.error(f"센서 종류 '{sensor_type}'에 해당하는 URL이 없습니다.")
        return
        
    logger.debug(f"선택된 서버 URL: {backend_url}")
    
   # Payload 생성
    # nibp를 측정하는 데 필요한 속성의 수가 2개로 지정되어 있어서 payload가 다름. 
    if sensor_type == "nibp":
        # NIBP 데이터는 항상 수축기와 이완기 쌍으로 전송
        payload = {
            "device_id": device_id,
            "userid": username,
            "systolic": data[0], # 수축기
            "diastolic": data[1] # 이완기
        }
    else:
        # 다른 센서 데이터 처리(일반적으로 보내는 데이터 속성이 1개인 센서 값)
        payload = {
            "device_id": device_id,
            "userid": username,
            f"{sensor_type}data": data
        }
    
    # Payload 생성 로그
    logger.debug(f"device_id: {payload['device_id']}, userid: {payload['userid']}")
    response = None  # response를 초기화
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
