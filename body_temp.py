@temp_router.websocket("/ws/body_temp")
async def body_temp_websocket(websocket: WebSocket):
    """
    Body Temperature 센서 데이터를 수신하고 처리하는 WebSocket 엔드포인트.
    - 텍스트 메시지 "USER:user1"을 통해 사용자 인증을 수행.
    - 바이너리 데이터를 통해 체온 데이터를 수신.
    - "GET" 메시지를 통해 현재 큐의 데이터를 반환.
    """
    await websocket.accept()
    user_name = None  # 사용자 이름 초기화

    try:
        while True:
            # 메시지 수신
            try:
                message = await websocket.receive_text()  # 텍스트 메시지 처리
                if message.startswith("USER:"):
                    # 사용자 이름 설정
                    user_name = message.split("USER:")[1]
                    logger.info(f"사용자 정보 수신: {user_name}")

                    # 사용자 검증
                    valid_users = {"user1", "user2", "user3"}  # 인증 가능한 사용자 목록
                    if user_name in valid_users:
                        await websocket.send_text("사용자 인증 성공")
                        logger.info(f"사용자 '{user_name}' 인증 성공")
                    else:
                        await websocket.send_text("유효하지 않은 사용자입니다.")
                        logger.warning(f"사용자 '{user_name}' 인증 실패")
                        # 인증 실패 시 연결 종료
                        await websocket.close(code=1008)  # 정책 위반 (Policy Violation)
                        logger.info("유효하지 않은 사용자로 인해 WebSocket 연결이 종료되었습니다.")
                        break

                elif message == "GET":
                    if temperature_data_queue:
                        # 큐에 저장된 모든 데이터를 전송
                        data_to_send = list(temperature_data_queue)
                        await websocket.send_text(f"현재 체온 데이터: {data_to_send}")
                        logger.info("클라이언트에게 현재 체온 데이터를 전송했습니다.")

                        # 데이터 전송 후 큐 초기화
                        temperature_data_queue.clear()
                        logger.info("체온 데이터 큐가 초기화되었습니다.")
                    else:
                 
