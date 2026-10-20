# task-flow

개인용 Task 관리 웹 앱. 카드를 만들고 상태(할 일 · 진행 중 · 완료)를 직접 바꾸며 한눈에 본다.

## 지금 되는 것
- 카드 등록, 수정, 삭제(삭제 전 확인 한 번), 상태 변경(어느 상태로든)
- 상태별 3열 보기
- 데이터는 내 컴퓨터의 SQLite 파일(`backend/taskflow.db`)에 저장되어 앱을 껐다 켜도 남는다.

## 아직 없는 것
- 검색과 필터(R-007): 검색 대상과 필터 조건이 정해지지 않았다(Q-5).

## 구조
- `frontend/` 화면 (React · Vite · TypeScript)
- `backend/` API (FastAPI, Python 3.12, uv)
- 설계 문서: PRD.md, ARCHITECTURE.md, DECISIONS.md, USER-WORKFLOW.md, SCREEN-SPEC.md, API-SPEC.md

## 실행 (터미널 두 개)
```
cd backend  && uv run uvicorn app.main:app --port 8000
cd frontend && npm install && npm run dev
```
브라우저에서 http://localhost:5173 을 연다.

DB 파일 위치는 환경변수 `TASKFLOW_DB`로 바꿀 수 있다.

## 테스트 (백엔드)
```
cd backend && uv run python -m unittest discover -s tests -t .
```
