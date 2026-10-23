# task-flow

개인용 Task 관리 웹 앱. 카드를 만들고 상태(할 일 · 진행 중 · 완료)를 직접 바꾸며 한눈에 본다.

## 지금 되는 것
- 카드 등록, 수정, 삭제(삭제 전 확인 한 번), 상태 변경(어느 상태로든)
- 상태별 3열 보기
- 데이터는 내 컴퓨터의 SQLite 파일(`backend/taskflow.db`)에 저장되어 앱을 껐다 켜도 남는다.
- 가입 · 로그인 · 로그아웃 · 현재 사용자 API(`/auth/*`). 모든 Task API는 로그인이 필요하고, 로그인한 사람은 자기 Task만 본다(R-008).
- 로그인 · 가입 화면: 로그인하지 않았거나 로그인이 끝나면(30분) 로그인 화면이 나온다. 로그인하면 보드가 나오고, 위쪽의 로그아웃 버튼으로 나갈 수 있다(D-032, D-033).

## 아직 없는 것
- 검색과 필터(R-007): 검색 대상과 필터 조건이 정해지지 않았다(Q-5).
- 비밀번호 찾기, 소셜 로그인, 팀 공유는 만들지 않는다.

## 구조
- `frontend/` 화면 (React · Vite · TypeScript)
- `backend/` API (FastAPI, Python 3.12, uv)
- 설계 문서: PRD.md, ARCHITECTURE.md, DECISIONS.md, USER-WORKFLOW.md, SCREEN-SPEC.md, API-SPEC.md, API-SPEC-CHANGE.md · DATA-MIGRATION-PLAN.md (로그인, #6)

## 처음 한 번: 세션 비밀값
`backend/.env`의 `SESSION_SECRET=` 뒤에 비밀값을 직접 넣는다. 이 값이 비어 있으면 API는 시작하지 않는다. `.env`는 Git에 넣지 않는다.
```
cd backend && uv run python -c "import secrets; print(secrets.token_urlsafe(48))"
```
출력된 값을 `.env`에 붙여 넣는다. 값을 바꾸면 로그인한 사람은 모두 로그아웃된다.

## 실행 (터미널 두 개)
```
cd backend  && uv run uvicorn app.main:app --port 8000
cd frontend && npm install && npm run dev
```
브라우저에서 http://localhost:5173 을 연다.

DB 파일 위치는 환경변수 `TASKFLOW_DB`로 바꿀 수 있다.

## 기존 DB 이전 (로그인 도입, #6)
로그인을 넣기 전에 만든 `taskflow.db`(Task에 주인이 없는 DB)는 앱이 시작하지 않는다. 아래 순서로 alembic으로 이전한다. 자세한 계획은 DATA-MIGRATION-PLAN.md 6절, 결정은 DECISIONS.md D-030.
이전을 하면 모든 기존 Task는 `migrated@test.com` 계정이 가진다. 이 계정은 처음에는 로그인할 수 없고, 이 이메일로 **처음 가입하는 사람**이 비밀번호를 정해 계정과 Task를 받는다. 이메일 확인이 없으므로 이전 직후 본인이 바로 가입한다.

1. API 서버를 멈춘다.
2. 백업한다. `taskflow.db`를 다른 이름(예: `taskflow.backup.db`)으로 복사한다. `*.db`는 Git에 들어가지 않는다.
3. 백업의 값을 기록한다. 아래 명령은 Task 수와 id · title · description · status의 요약값을 출력한다.
   ```
   cd backend
   uv run python -c "import sqlite3,sys,hashlib;c=sqlite3.connect(sys.argv[1]);r=c.execute('SELECT id,title,description,status FROM tasks ORDER BY id').fetchall();print(len(r),hashlib.sha256(repr(r).encode()).hexdigest())" taskflow.backup.db
   ```
4. (권장) 복사본으로 먼저 연습한다. `TASKFLOW_DB`를 복사본 경로로 지정하면 실제 DB는 건드리지 않는다. PowerShell:
   ```
   Copy-Item taskflow.backup.db practice.db
   $env:TASKFLOW_DB = "practice.db"; uv run alembic upgrade head; Remove-Item Env:TASKFLOW_DB
   ```
   `alembic`은 실행할 때마다 `[alembic] 대상 DB: …` 경로를 출력한다. 경로가 의도한 파일인지 확인한다. **`TASKFLOW_DB`를 지정하지 않으면 실제 `backend/taskflow.db`가 대상이다.**
5. 실제 DB에 적용한다.
   ```
   cd backend && uv run alembic upgrade head
   ```
   리비전 하나씩 보려면 `uv run alembic upgrade 0001`, `0002`, `0003`, `0004` 순서로 나누어 실행한다. 각 리비전은 끝에서 수량 · id · 값을 확인하고, 맞지 않으면 그 리비전의 변경을 취소하고 멈춘다.
6. 3번의 명령을 `taskflow.db`에 같은 방법으로 실행해 백업과 같은 두 값(수, 요약값)이 나오는지 확인한다. 하나라도 다르면 7번으로 간다.
7. 되돌리기: API를 멈추고 `taskflow.db`를 백업 파일로 바꾼다. 이전한 뒤 가입한 사용자와 만든 Task는 사라진다. 파일을 덮어쓰기 전에 대상을 확인한다. (다운그레이드 명령은 지원하지 않는다.)
8. `SESSION_SECRET`을 채우고 API를 시작한 뒤, `migrated@test.com`으로 가입하고 로그인해서 기존 Task가 모두 보이는지 확인한다.
9. 확인이 끝나기 전에는 백업을 지우지 않는다.

이전은 옛 구조의 DB 전용이다. 새 DB는 앱을 처음 시작할 때 새 구조로 만들어진다.

## 테스트 (백엔드)
```
cd backend && uv run python -m unittest discover -s tests -t .
```
