"""m2 D1 add users sessions and nullable owner_id

Revision ID: 0001
Revises:
Create Date: 2026-10-22 17:23:46.000000

DATA-MIGRATION-PLAN.md 6절 D1 구조 추가.
users · sessions 를 만들고 tasks 에 owner_id 를 NULL 허용으로 더한다.
"""
from typing import Sequence, Union

from alembic import op

from migrations.m2_common import DOWNGRADE_MESSAGE, columns, require, snapshot, table_names

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # 이 이전은 옛 구조(owner_id 가 없는 tasks)의 DB 전용이다. 새 DB 는 앱이 시작할 때 만든다.
    tables = table_names(conn)
    require("tasks" in tables, "tasks 테이블이 없다. 새 DB 는 앱을 시작하면 만들어지므로 이전이 필요 없다.")
    require(
        "owner_id" not in columns(conn, "tasks"),
        "tasks 에 이미 owner_id 가 있다. 이미 새 구조라면 `alembic stamp head` 로 표시만 한다.",
    )
    require(
        "users" not in tables and "sessions" not in tables,
        "users 나 sessions 가 이미 있다. 일부만 적용된 DB 이므로 백업에서 다시 시작한다.",
    )

    before = snapshot(conn)

    # app/db.py 의 init_db 와 같은 정의이다. (test_migrations 가 최종 구조가 같은지 비교한다)
    conn.exec_driver_sql(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT
        )
        """
    )
    conn.exec_driver_sql(
        """
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            expires_at INTEGER NOT NULL
        )
        """
    )
    conn.exec_driver_sql("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")

    # 확인: Task 수 · id · 값이 그대로이고, 주인 없는 Task 수가 전체 Task 수와 같다.
    require(snapshot(conn) == before, "D1 뒤 Task 의 id 나 값이 달라졌다.")
    unowned = conn.exec_driver_sql("SELECT COUNT(*) FROM tasks WHERE owner_id IS NULL").scalar()
    require(unowned == len(before), "D1 뒤 주인 없는 Task 수가 전체 Task 수와 다르다.")


def downgrade() -> None:
    raise NotImplementedError(DOWNGRADE_MESSAGE)
