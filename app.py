from fastapi import APIRouter

router = APIRouter()

@router.get("/sensor-data")
async def get_sensor_data():
    return {"message": "센서 데이터가 여기에 표시됩니다."}
