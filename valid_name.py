from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import logging
# import asyncio
from .user_state import current_username, lock  # 상태 변수와 Lock 가져오기

# 로깅 설정
logger = logging.getLogger("valid_logger")

valid_router = APIRouter()

# 테스트용 사용자 데이터베이스
valid_users = {"user1", "user2", "user3"}

@valid_router.websocket("/ws/validate_user")
async def validate_user(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            user_name = await websocket.receive_text()
            logger.info(f"받은 사용자 이름: {user_name}")

            async with lock:  # 동시성 보호
                global current_username
                current_username = user_name

            if user_name in valid_users:
                response = "valid"
                logger.info(f"사용자 검증 성공: {user_name}")
            else:
                response = "invalid"
                logger.warning(f"사용자 검증 실패: {user_name}")

            await websocket.send_text(response)
    except WebSocketDisconnect:
        logger.info("클라이언트가 연결을 끊었습니다.")
    except Exception as e:
        logger.error(f"오류 발생: {e}")

# 저장된 username 값을 조회하는 엔드포인트 (GET)
@valid_router.get("/validate_user")
async def get_validate_user():
    """
    저장된 가장 최근 사용자 이름을 반환합니다.
    """
    global current_username
    if not current_username:
        return {"message": "저장된 유저 정보가 없습니다."}
    
    return {
        "message": "유저 정보 데이터 조회 성공",
        "User Name": current_username
    }

