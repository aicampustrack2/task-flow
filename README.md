# task-flow

개인용 Task 관리 웹 앱. 지금은 M0(프로젝트 기본 구조)까지만 있다.

## 구조
- `frontend/` 화면 (React · Vite · TypeScript)
- `backend/` API (FastAPI, Python 3.12, uv)
- 설계 문서: PRD.md, ARCHITECTURE.md, DECISIONS.md

## 실행 (터미널 두 개)
```
cd backend  && uv run uvicorn app.main:app --port 8000
cd frontend && npm install && npm run dev
```
브라우저에서 http://localhost:5173 을 열면 "API 연결: 연결됨"이 보인다.
