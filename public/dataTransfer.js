// 웹소켓 연결
const socket = new WebSocket('wss://port-0-iot-healthcare-1272llwukgaeg.sel5.cloudtype.app/ws/body_temp');

// 웹소켓 연결 성공 시
socket.onopen = () => {
    console.log('WebSocket connection established');
};

// 메시지를 수신했을 때
socket.onmessage = (event) => {
    // event.data에서 "Sent temperature: " 이후의 값만 추출
    const message = event.data;
    const tempData = message.replace('Sent temperature: ', ''); // "Sent temperature: " 제거
    console.log(`Received temperature: ${tempData}`);
    
    // 온도 데이터를 화면에 출력하는 코드 추가 (예: HTML 요소에 삽입)
    document.getElementById('temperatureDisplay').innerText = `Current Temperature: ${tempData} °C`;
};

// 웹소켓 연결 종료 시
socket.onclose = () => {
    console.log('WebSocket connection closed');
};

// 에러 발생 시
socket.onerror = (error) => {
    console.error('WebSocket error:', error);
};
