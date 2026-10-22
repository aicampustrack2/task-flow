"""m2 D3 hand over tasks to migrated account

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-22 17:23:46.000000

DATA-MIGRATION-PLAN.md 6절 D3 Task 넘기기 (D-024).
주인 없는 Task 를 모두 이전용 계정에 넘긴다.
"""
from typing import Sequence, Union

from alembic import op

from migrations.m2_common import DOWNGRADE_MESSAGE, MIGRATED_USERNAME, require, snapshot

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    ids = conn.exec_driver_sql(
        "SELECT id FROM users WHERE username = ?", (MIGRATED_USERNAME,)
    ).fetchall()
    require(len(ids) == 1, "이전용 계정이 정확히 하나가 아니다.")
    migrated_id = ids[0][0]

    before = snapshot(conn)
    conn.exec_driver_sql(
        "UPDATE tasks SET owner_id = ? WHERE owner_id IS NULL", (migrated_id,)
    )

    # 확인: 주인 없는 Task 가 0건이고, 모든 Task 의 주인이 이전용 계정이며, 수 · id · 값이 그대로이다.
    unowned = conn.exec_driver_sql("SELECT COUNT(*) FROM tasks WHERE owner_id IS NULL").scalar()
    require(unowned == 0, "D3 뒤에도 주인 없는 Task 가 있다.")
    others = conn.exec_driver_sql(
        "SELECT COUNT(*) FROM tasks WHERE owner_id != ?", (migrated_id,)
    ).scalar()
    require(others == 0, "이전용 계정이 아닌 주인의 Task 가 있다.")
    require(snapshot(conn) == before, "D3 뒤 Task 의 id 나 값이 달라졌다.")


def downgrade() -> None:
    raise NotImplementedError(DOWNGRADE_MESSAGE)
