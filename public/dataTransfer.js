// WebSocket 서버에 연결하기 위해 WebSocket 객체 생성
const socket_temp = new WebSocket("wss://your-cloud-server-address/ws/body_temp");

// WebSocket 연결이 성공적으로 열리면 실행되는 함수
socket.onopen = () => {
    // 연결 상태를 사용자에게 알림
    document.getElementById("status").innerText = "Connected to WebSocket";
    // 콘솔에 연결 성공 메시지 출력
    console.log("WebSocket connection opened."); 
};

// 서버로부터 메시지를 받을 때 실행되는 함수
socket.onmessage = (event) => {
    // 수신된 데이터 가져오기
    const receivedData = event.data;
    // 수신된 데이터를 웹 페이지에 출력
    document.getElementById("receivedData").innerText = `Received data: ${receivedData}`;
    // 콘솔에 수신된 데이터 출력
    console.log("Received data:", receivedData); 
};

// WebSocket 연결이 종료되면 실행되는 함수
socket.onclose = () => {
    // 연결 종료 상태를 사용자에게 알림
    document.getElementById("status").innerText = "WebSocket connection closed";
    // 콘솔에 연결 종료 메시지 출력
    console.log("WebSocket connection closed."); 
};
