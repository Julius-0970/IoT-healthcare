from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from logger import get_logger  # 별도의 로깅 설정 가져오기
from user_state import current_username, lock  # 상태 변수와 Lock 가져오기

# 로거 생성
logger = get_logger("valid_logger")

valid_router = APIRouter()

# 테스트용 사용자 데이터베이스
valid_users = {"user1", "user2", "user3", "example_user"}

@valid_router.websocket("/ws/validate_user")
async def validate_user(websocket: WebSocket):
    """
    클라이언트로부터 사용자 이름을 받아 유효성을 확인하고, 
    전역 변수 current_username에 저장하는 WebSocket 엔드포인트.
    """
    await websocket.accept()
    try:
        while True:
            user_name = await websocket.receive_text()
            logger.info(f"받은 사용자 이름: {user_name}")

            # Lock 상태 확인
            if lock.locked():
                logger.warning("Lock이 이미 획득된 상태입니다. 대기 중...")

            # 동시성 보호 및 글로벌 변수 업데이트
            async with lock:
                logger.info("Lock을 획득했습니다.")
                global current_username
                current_username = user_name
                logger.info(f"current_username이 업데이트되었습니다: {current_username}")
            logger.info("Lock이 해제되었습니다.")

            # 사용자 유효성 검사
            if user_name in valid_users:
                response = "valid"
                logger.info(f"사용자 검증 성공: {user_name}")
            else:
                response = "invalid"
                logger.warning(f"사용자 검증 실패: {user_name}")

            # 검증 결과 전송
            await websocket.send_text(response)
    except WebSocketDisconnect:
        logger.info("클라이언트가 연결을 끊었습니다.")
    except Exception as e:
        logger.error(f"오류 발생: {e}")


@valid_router.get("/validate_user")
async def get_validate_user():
    """
    저장된 가장 최근 사용자 이름을 반환합니다.
    """
    # Lock 상태 확인
    if lock.locked():
        logger.warning("GET 요청 시 Lock이 획득된 상태입니다. 대기 중...")
    
    global current_username
    logger.info(f"현재 저장된 사용자 이름 조회 요청: {current_username}")
    if not current_username:
        return {"message": "저장된 유저 정보가 없습니다."}
    
    return {
        "message": "유저 정보 데이터 조회 성공",
        "User Name": current_username
    }

