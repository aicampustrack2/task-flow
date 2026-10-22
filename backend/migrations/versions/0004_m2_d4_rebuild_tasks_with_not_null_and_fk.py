"""m2 D4 rebuild tasks with NOT NULL and FK

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-22 17:23:46.000000

DATA-MIGRATION-PLAN.md 6절 D4 NOT NULL 과 외래 키 적용 (D-023).
SQLite 는 기존 컬럼에 NOT NULL 과 외래 키를 더할 수 없어서, 새 테이블을 만들어 복사하고 바꾼다.
"""
from typing import Sequence, Union

from alembic import op

from migrations.m2_common import DOWNGRADE_MESSAGE, columns, require, snapshot

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, Sequence[str], None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    unowned = conn.exec_driver_sql("SELECT COUNT(*) FROM tasks WHERE owner_id IS NULL").scalar()
    require(unowned == 0, "주인 없는 Task 가 남아 있어 NOT NULL 을 적용할 수 없다.")

    before = snapshot(conn)
    # AUTOINCREMENT 의 다음 id 기록. 새 테이블로 옮기면 가장 큰 id 로 줄어들 수 있어 따로 보존한다.
    old_seq = conn.exec_driver_sql("SELECT seq FROM sqlite_sequence WHERE name = 'tasks'").scalar()

    # app/db.py 의 init_db 와 같은 정의이다. (test_migrations 가 최종 구조가 같은지 비교한다)
    conn.exec_driver_sql(
        """
        CREATE TABLE tasks_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL,
            owner_id INTEGER NOT NULL REFERENCES users(id)
        )
        """
    )
    # id 를 그대로 가져간다.
    conn.exec_driver_sql(
        "INSERT INTO tasks_new (id, title, description, status, owner_id) "
        "SELECT id, title, description, status, owner_id FROM tasks ORDER BY id"
    )
    require(snapshot(conn, "tasks_new") == before, "복사한 Task 의 수 · id · 값이 원본과 다르다.")

    conn.exec_driver_sql("DROP TABLE tasks")
    conn.exec_driver_sql("ALTER TABLE tasks_new RENAME TO tasks")
    conn.exec_driver_sql("CREATE INDEX idx_tasks_owner_id ON tasks(owner_id)")

    if old_seq is not None:
        updated = conn.exec_driver_sql(
            "UPDATE sqlite_sequence SET seq = MAX(seq, ?) WHERE name = 'tasks'", (old_seq,)
        ).rowcount
        if updated == 0:
            conn.exec_driver_sql(
                "INSERT INTO sqlite_sequence (name, seq) VALUES ('tasks', ?)", (old_seq,)
            )

    # 확인: 수량 비교 ②와 외래 키 검사 0건.
    require(snapshot(conn) == before, "D4 뒤 Task 의 수 · id · 값이 달라졌다.")
    owner = columns(conn, "tasks").get("owner_id")
    require(owner is not None and owner[1] == 1, "D4 뒤 owner_id 가 NOT NULL 이 아니다.")
    violations = conn.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
    require(not violations, f"외래 키 검사에서 위반 {len(violations)}건이 나왔다.")


def downgrade() -> None:
    raise NotImplementedError(DOWNGRADE_MESSAGE)
