# 이름 검증
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import logging 

# 로깅 설정
logger = logging.getLogger(__name__)

# APIRouter 인스턴스 생성
valid_router = APIRouter()


# 테스트용 사용자 데이터베이스 (예: 실제로는 데이터베이스를 사용)
valid_users = {"user1", "user2", "user3"}  # 검증에 사용할 사용자 목록

@valid_router.websocket("/ws/validate_user")
async def validate_user(websocket: WebSocket):
    """
    WebSocket 경로로 사용자 이름을 검증합니다.
    클라이언트에서 사용자 이름을 보내면, 서버는 'valid' 또는 'invalid' 응답을 반환합니다.
    """
    await websocket.accept()
    try:
        while True:
            # 클라이언트로부터 메시지(사용자 이름) 수신
            user_name = await websocket.receive_text()
            logger.info(f"받은 사용자 이름: {user_name}")
            
            # 사용자 검증
            if user_name in valid_users:
                response = "valid"
                logger.info(f"사용자 검증 성공: {user_name}")
            else:
                response = "invalid"
                logger.warning(f"사용자 검증 실패: {user_name}")
            
            # 검증 결과 클라이언트로 전송
            await websocket.send_text(response)
    except WebSocketDisconnect:
        logger.info("클라이언트가 연결을 끊었습니다.")
    except Exception as e:
        logger.error(f"오류 발생: {e}")
