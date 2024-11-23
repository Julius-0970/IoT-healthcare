import asyncio

# 공유 상태 변수와 Lock
current_username = None
lock = asyncio.Lock()  # 동시성을 보호하기 위한 Lock
