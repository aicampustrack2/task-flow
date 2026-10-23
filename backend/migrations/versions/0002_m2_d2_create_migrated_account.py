"""m2 D2 create migrated account

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-22 17:23:46.000000

DATA-MIGRATION-PLAN.md 6절 D2 이전용 계정 만들기 (D-024).
migrated@test.com 계정을 비밀번호 없이(password_hash NULL) 만든다.
비밀번호가 없으면 로그인할 수 없고, 이 이메일로 처음 가입하는 사람이 비밀번호를 정해 받는다.
"""
from typing import Sequence, Union

from alembic import op

from migrations.m2_common import DOWNGRADE_MESSAGE, MIGRATED_USERNAME, require

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # 같은 이메일의 사용자가 이미 있거나 다른 사용자가 있으면 아무것도 바꾸지 않고 멈춘다.
    count = conn.exec_driver_sql("SELECT COUNT(*) FROM users").scalar()
    require(count == 0, "users 에 이미 사용자가 있다. 이전용 계정을 만들지 않고 멈춘다.")

    conn.exec_driver_sql(
        "INSERT INTO users (username, password_hash) VALUES (?, NULL)", (MIGRATED_USERNAME,)
    )

    # 확인: users 가 정확히 한 명(이전용 계정)이고, 비밀번호가 없어 로그인할 수 없다.
    rows = conn.exec_driver_sql("SELECT username, password_hash FROM users").fetchall()
    require(
        [tuple(r) for r in rows] == [(MIGRATED_USERNAME, None)],
        "D2 뒤 users 가 이전용 계정 한 명이 아니다.",
    )


def downgrade() -> None:
    raise NotImplementedError(DOWNGRADE_MESSAGE)
