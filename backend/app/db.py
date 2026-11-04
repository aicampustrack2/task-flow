import os
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from app.config import get_database_url

# 예전 SQLite 파일 경로. 앱은 더 쓰지 않고 migrations/env.py(alembic)만 쓴다.
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "taskflow.db"

# 테이블은 supabase/schema.sql 이 만든다. 이 열 중 하나라도 없으면 시작하지 않는다. (D-023, #19)
REQUIRED_COLUMNS = {
    "users": ("id", "username", "password_hash"),
    "sessions": ("id", "user_id", "expires_at"),
    "tasks": ("id", "title", "description", "status", "owner_id", "priority", "due_date"),
}


class MigrationRequired(RuntimeError):
    """필요한 테이블이나 열이 없다. supabase/apply_schema.py 로 스키마를 먼저 만들어야 한다."""


def get_db_path() -> Path:
    return Path(os.environ.get("TASKFLOW_DB", DEFAULT_DB_PATH))


def connect() -> psycopg.Connection:
    # autocommit 이라 저장이 필요한 곳은 with conn.transaction(): 으로 묶는다.
    # prepare_threshold=None: 트랜잭션 풀러(6543)에서도 쓸 수 있게 서버 측 준비 구문을 끈다.
    return psycopg.connect(
        get_database_url(), row_factory=dict_row, autocommit=True, prepare_threshold=None
    )


def init_db() -> None:
    # 저장소는 보관만 맡는다. 규칙 판단은 API 쪽(rules.py)에서 한다.
    # 테이블은 만들지 않는다. 열이 있는지만 확인한다.
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT table_name, column_name FROM information_schema.columns"
            " WHERE table_schema = 'public' AND table_name = ANY(%s)",
            (list(REQUIRED_COLUMNS),),
        ).fetchall()
    finally:
        conn.close()
    present = {(r["table_name"], r["column_name"]) for r in rows}
    missing = [
        f"{table}.{col}"
        for table, cols in REQUIRED_COLUMNS.items()
        for col in cols
        if (table, col) not in present
    ]
    if missing:
        raise MigrationRequired(
            f"{', '.join(missing)} 이(가) 없습니다. supabase/apply_schema.py 로 스키마를 먼저 만드세요."
        )
