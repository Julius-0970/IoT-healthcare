import logging

def get_logger(name: str):
    """
    지정된 이름으로 로거를 생성하고 반환합니다.
    :param name: 로거의 이름
    :return: 로거 객체
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # 콘솔 출력 핸들러
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)

    # 로그 메시지 형식
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s")
    console_handler.setFormatter(formatter)

    # 핸들러가 중복 추가되지 않도록 체크
    if not logger.handlers:
        logger.addHandler(console_handler)

    return logger
