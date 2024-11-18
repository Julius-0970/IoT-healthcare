from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import logging
import asyncio

# 로깅 설정
logger = logging.getLogger("valid_logger")

# APIRouter 인스턴스 생성
valid_router = APIRouter()

# 테스트용 사용자 데이터베이스 (예: 실제로는 데이터베이스를 사용)
valid_users = {"user1", "user2", "user3"}  # 검증에 사용할 사용자 목록

# 사용자 이름을 저장할 큐
username_queue = asyncio.Queue()

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
            
            # 사용자 이름 큐에 추가
            await username_queue.put(user_name)
            logger.debug(f"큐에 추가된 사용자 이름: {user_name}")
    except WebSocketDisconnect:
        logger.info("클라이언트가 연결을 끊었습니다.")
    except Exception as e:
        logger.error(f"오류 발생: {e}")


# 저장된 username 값을 조회하는 엔드포인트 (GET)
@valid_router.get("/validate_user")
async def get_validate_user():
    """
    저장된 검증된 사용자 이름을 반환합니다.
    """
    users = []
    while not username_queue.empty():
        users.append(await username_queue.get())  # 큐에서 데이터를 꺼냄
    
    if not users:
        return {"message": "저장된 유저 정보가 없습니다."}
    
    return {
        "message": "유저 정보 데이터 조회 성공",
        "User Names": users
    }


"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import logging
import asyncio
import httpx

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("valid_logger")

# APIRouter 인스턴스 생성
valid_router = APIRouter()

# 사용자 이름을 저장할 큐
username_queue = asyncio.Queue()

# 백엔드 서버의 엔드포인트 URL 설정 (실제 백엔드 서버의 URL로 변경)
BACKEND_SERVER_URL = "http://localhost:8001/api/receive_username"

@valid_router.websocket("/ws/validate_user")
async def validate_user(websocket: WebSocket):
    """
    WebSocket 경로로 사용자 이름을 받아 백엔드 서버로 전송합니다.
    백엔드 서버의 응답에 따라 'valid' 또는 'invalid' 응답을 클라이언트로 반환합니다.
    """
    await websocket.accept()
    logger.info("클라이언트 연결 수락됨.")
    try:
        while True:
            # 클라이언트로부터 메시지(사용자 이름) 수신
            user_name = await websocket.receive_text()
            logger.info(f"받은 사용자 이름: {user_name}")
            
            # 백엔드 서버로 사용자 이름 전송
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        BACKEND_SERVER_URL,
                        json={"username": user_name}
                    )
                response.raise_for_status()  # HTTP 오류 발생 시 예외 발생
                backend_response = response.json()
                logger.info(f"백엔드 서버 응답: {backend_response}")
                
                # 백엔드 서버의 응답에 따라 클라이언트에 응답 전송
                if backend_response.get("status") == "valid":
                    await username_queue.put(user_name)
                    await websocket.send_text("valid")
                    logger.info(f"사용자 검증 성공: {user_name}")
                else:
                    await websocket.send_text("invalid")
                    logger.warning(f"사용자 검증 실패: {user_name}")
            except httpx.HTTPError as http_err:
                logger.error(f"백엔드 서버에 데이터 전송 실패: {http_err}")
                await websocket.send_text("backend_error")
            except Exception as e:
                logger.error(f"예상치 못한 오류 발생: {e}")
                await websocket.send_text("server_error")
    except WebSocketDisconnect:
        logger.info("클라이언트가 연결을 끊었습니다.")
    except Exception as e:
        logger.error(f"오류 발생: {e}")

# 저장된 username 값을 조회하는 엔드포인트 (GET)
@valid_router.get("/validate_user")
async def get_validate_user():
    """
    저장된 검증된 사용자 이름을 반환합니다.
    """
    users = []
    while not username_queue.empty():
        users.append(await username_queue.get())  # 큐에서 데이터를 꺼냄
    
    if not users:
        return {"message": "저장된 유저 정보가 없습니다."}
    
    return {
        "message": "유저 정보 데이터 조회 성공",
        "User Names": users
    }
"""
