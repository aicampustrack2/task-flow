import os
import sqlite3
from pathlib import Path

# 기본 DB 파일은 backend/taskflow.db (*.db 는 .gitignore). 환경변수로 바꿀 수 있다.
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "taskflow.db"


def get_db_path() -> Path:
    return Path(os.environ.get("TASKFLOW_DB", DEFAULT_DB_PATH))


def connect(path: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db(path: Path | None = None) -> None:
    # 저장소는 보관만 맡는다. 규칙 판단은 API 쪽(rules.py)에서 한다.
    with connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL
            )
            """
        )
    conn.close()
