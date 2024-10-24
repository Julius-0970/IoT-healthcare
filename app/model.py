from pydantic import BaseModel

class SensorData(BaseModel):
    airflow: float # 호흡 측정값 
    eog: float     # 안구 움직임 측정값
    ecg: float     # 심장 박동 측정값
    emg: float     # 근육 활성도 측정값
    gsr: float     # 거짓말 탐지기값

    body_temp: int        # 체온 측정값
    nibp_systolic: int    # 혈압 수축기 측정값
    inbp_diastolic: int   # 혈압 이완기 측정값
    spO2: int             # 혈당(%) 측정값
    bpm: int              # 심박수 측정값