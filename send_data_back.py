# 모든 센서값이 들어오는 경우, 백엔드로 데이터랑 이름 전송하는 로직.

import httpx
from config.logger import get_logger

logger = get_logger("data_sender")

async def send_data_to_backend(username, data_queue, backend_url):
    if not username:
        logger.warning("사용자 이름이 설정되지 않았습니다.")
        return

    if not data_queue:
        logger.warning("전송할 데이터가 없습니다.")
        return

    payload = {
        "username": username,
        "ecg_data": list(data_queue)
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(backend_url, json=payload)
            if response.status_code == 200:
                logger.info("데이터 전송 성공")
                data_queue.clear()
            else:
                logger.error(f"데이터 전송 실패: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"데이터 전송 중 오류 발생: {e}")
