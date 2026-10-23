import os
import sqlite3
from pathlib import Path

# 기본 DB 파일은 backend/taskflow.db (*.db 는 .gitignore). 환경변수로 바꿀 수 있다.
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "taskflow.db"


class MigrationRequired(RuntimeError):
    """owner_id 가 없는 예전 tasks 테이블이다. alembic upgrade 로 먼저 이전해야 한다."""


def get_db_path() -> Path:
    return Path(os.environ.get("TASKFLOW_DB", DEFAULT_DB_PATH))


def connect(path: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or get_db_path())
    conn.row_factory = sqlite3.Row
    # SQLite 는 외래 키 검사를 연결마다 켜야 한다. (D-023)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path: Path | None = None) -> None:
    # 저장소는 보관만 맡는다. 규칙 판단은 API 쪽(rules.py)에서 한다.
    # 예외: tasks.owner_id 는 NOT NULL + 외래 키로 저장소가 막는다. (D-023)
    conn = connect(path)
    try:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(tasks)")]
        if cols and "owner_id" not in cols:
            # 기존 DB 는 이 함수가 바꾸지 않는다. 백업 후 alembic 으로만 바꾼다.
            raise MigrationRequired(
                "tasks 테이블에 owner_id 가 없습니다. 백업 후 alembic upgrade 로 이전하세요."
            )
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    expires_at INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    owner_id INTEGER NOT NULL REFERENCES users(id)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_owner_id ON tasks(owner_id)"
            )
    finally:
        conn.close()
