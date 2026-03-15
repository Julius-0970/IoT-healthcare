# 🏥 Healthcare DAQ FastAPI Server

> Raspberry Pi 클라이언트로부터 생체신호 패킷을 WebSocket으로 수신하고, 센서별로 파싱하여 백엔드 서버로 전송하는 FastAPI 중계 서버

<br>

## 📖 프로젝트 배경

원래는 WebSocket 실시간 스트리밍으로 설계했으나, **팀장의 지시로 HTTP POST 기반의 배치 전송 방식으로 변경**했습니다. IoT 장비의 실시간 스트림을 일정량 큐에 누적한 뒤 배치로 변환하여 전송하는 방식을 채택했으며, 이 변환을 담당하는 중간 프록시 서버로 본 FastAPI 서버를 구성했습니다.

패킷 해석 방식 역시 원래 C++로 정의된 프로토콜을 기반으로, **Python으로 직접 재분석하여 구현**했습니다.

<br>

## 🛠 기술 스택

| 분류 | 기술 |
|------|------|
| Language | Python 3.8+ |
| Framework | FastAPI 0.82.0 |
| 비동기 처리 | asyncio, uvicorn |
| HTTP 클라이언트 | httpx (비동기 POST) |
| 통신 | WebSockets 10.3 |
| 데이터 구조 | collections.deque, defaultdict |
| 로깅 | 커스텀 logger 모듈 |

<br>

## 🏗 시스템 아키텍처

```
Raspberry Pi  ──── WebSocket (wss://) ────►  FastAPI Server  ──── HTTP POST (JSON) ────►  Backend Server
(app.py)                                      패킷 파싱 · 큐 관리                          /ws/{sensor}
```

<br>

## 📂 파일 구조

```
├── main.py                  # FastAPI 앱 진입점, 라우터 등록
├── receive_and_parsing.py   # WebSocket 수신 · 패킷 파싱 · 큐 관리
├── send_to_data_back.py     # 파싱된 데이터를 백엔드로 POST 전송
├── logger.py                # 공통 로깅 설정
└── requirements.txt         # 의존성 목록
```

<br>

## 🔍 패킷 파싱 구조

Raspberry Pi로부터 수신한 패킷은 16진수 문자열로 변환된 뒤 아래 흐름으로 파싱됩니다.

```
수신 패킷 (bytes)
        │
        ▼
bytes.fromhex() → SOP / CMD / data_size / EOP 검증
        │
        ├── SOP != 0xF7 or EOP != 0xFA  →  파싱 중단
        ├── CMD 불일치                   →  파싱 중단
        │
        ├── packet_length == 10  →  정형 데이터 파싱 (SPO2 / NIBP / TEMP)
        └── packet_length == 86  →  비정형 데이터 파싱 (ECG / EMG / EOG / GSR / AIRFLOW)
```

### 패킷 검증 항목

| 위치 | 필드 | 기대값 |
|------|------|--------|
| `byte[0]` | SOP | `0xF7` |
| `byte[1]` | CMD | 센서별 응답 명령어 |
| `byte[2]` | data_size | 센서별 데이터 크기 |
| `byte[-1]` | EOP | `0xFA` |

<br>

## 🔬 센서별 파싱 로직

### 정형 데이터 (10 bytes)

| 센서 | CMD | 파싱 방식 |
|------|-----|----------|
| `SPO2` | `0x52` | `byte[5]` → 산소포화도 단일값 |
| `NIBP` | `0x42` | `byte[4]` 이완기, `byte[5]` 수축기 → 2개 값 |
| `TEMP` | `0xA2` | `byte[3:5]` + `byte[5:7]` → `(high + low) / 100.0 + 5` (float) |

### 비정형 데이터 (86 bytes)

ECG / EMG / EOG / GSR 는 동일한 파싱 방식을 사용합니다.

```python
data = raw_data_bytes[3:-1]  # SOP, CMD, data_size, EOP 제외한 순수 데이터

for i in range(0, len(data), 4):  # 4바이트 단위로 순회
    byte1 = data[i]
    byte2 = data[i + 1]
    fixed_value = int.from_bytes(data[i+2:i+4], byteorder="big")
    real_value = byte1 + byte2 + fixed_value
```

AIRFLOW는 2바이트 단위로 처리하며, `0xFFFF`(65535)인 경우 `-1`로 치환합니다.

```python
for i in range(0, len(data), 4):
    byte1 = int.from_bytes(data[i:i+2], byteorder="big")
    byte2 = int.from_bytes(data[i+2:i+4], byteorder="big")
    real_value = byte1 + byte2
    if real_value == 65535:  # 2의 보수 처리
        data_values.append(-1)
```

<br>

## 📬 센서별 설정

| 센서 | CMD | data_size | 큐 크기 | 비고 |
|------|-----|-----------|---------|------|
| `ECG` | `0x12` | `0x50` | 15,000 | 약 30초 분량 |
| `EMG` | `0x22` | `0x50` | 15,000 | |
| `EOG` | `0x32` | `0x50` | 15,000 | |
| `GSR` | `0x82` | `0x50` | 15,000 | |
| `AIRFLOW` | `0x62` | `0x50` | 15,000 | |
| `TEMP` | `0xA2` | `0x04` | 60 | |
| `NIBP` | `0x42` | `0x04` | 2 | 수축기 + 이완기 |
| `SPO2` | `0x52` | `0x04` | 10 | |

큐가 `maxlen`에 도달하면 자동으로 백엔드로 전송 후 WebSocket 연결을 종료합니다.

<br>

## 📤 백엔드 전송 페이로드

센서 종류에 따라 전송하는 JSON 페이로드 형태가 다릅니다.

```python
# NIBP — 수축기 / 이완기 쌍으로 전송
{ "device_id": "...", "userid": "...", "systolic": 120, "diastolic": 80 }

# SPO2 / TEMP — 리스트의 마지막 값만 전송
{ "device_id": "...", "userid": "...", "spo2data": 98 }

# ECG / EMG / EOG / GSR / AIRFLOW — 전체 리스트 전송
{ "device_id": "...", "userid": "...", "ecgdata": [1024, 1036, ...] }
```

<br>

## 🌐 API 엔드포인트

| 방식 | 경로 | 설명 |
|------|------|------|
| WebSocket | `/ws/{username}/{sensor_type}` | 센서 데이터 실시간 수신 |
| GET | `/{username}/{sensor_type}` | 현재 큐에 쌓인 데이터 조회 |

WebSocket 연결 직후 클라이언트는 `device_id` → `username` 순서로 두 번 텍스트를 전송해야 합니다.

<br>

## 📋 로깅

모든 이벤트는 콘솔에 출력됩니다.

```
[2024-01-01 12:00:00] INFO - WebSocket 연결 수락됨: 사용자=hong, 센서=ecg
[2024-01-01 12:00:00] INFO - 장치 ID 수신: aa:bb:cc:dd:ee:ff
[2024-01-01 12:00:01] INFO - [ecg] ECG 데이터 파싱 로직 실행
[2024-01-01 12:00:01] INFO - [ecg] 20개의 데이터가 저장되었습니다.
[2024-01-01 12:00:30] INFO - [ecg] 큐가 최대 용량에 도달했습니다. 백엔드로 데이터 전송 시도.
```
