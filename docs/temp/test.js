fetch('/api/tasks')          // 서버에 GET /api/tasks 요청을 보낸다. ==> 내 Task 목록을 가져온다.
    .then(r => r.json())     // 응답을 JSON으로 변환한다. 받은 답을 읽을 수 있는 데이터로 바꾼다.
    .then(console.log)          // 콘솔에 찍는다. ==> 브라우저 개발자 도구 콘솔에서 확인할 수 있다. 

fetch('/api/tasks/10', {    // 12번 Task를 수정한다. PATCH /api/tasks/12 요청을 보낸다.
    method: 'PATCH',        // HTTP 메서드 PATCH를 사용한다. ==> 일부만 수정할 때 사용한다.
    headers: { 'Content-Type': 'application/json' },    // 요청 헤더에 Content-Type을 application/json으로 설정한다. ==> 서버에 JSON 데이터를 보낸다는 의미이다.
    body: JSON.stringify({ title: '라이딩 연습' })  // 요청 본문에 JSON 데이터를 담는다. ==> title을 '라이딩 연습'으로 수정한다.,
}).then(r => console.log(r.status))     // 응답 상태 코드를 콘솔에 찍는다. ==> 200이면 성공, 401이면 인증 실패, 404이면 해당 Task가 없다는 의미이다.
