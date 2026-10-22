"""M2(로그인과 사용자별 Task) 이전 리비전이 함께 쓰는 확인 함수.

DATA-MIGRATION-PLAN.md 6절의 수량 비교 기준(C)을 리비전 안에서 확인한다.
확인이 맞지 않으면 예외를 내서 그 리비전의 변경을 모두 취소하고 멈춘다.
"""

MIGRATED_USERNAME = "migrated@test.com"

DOWNGRADE_MESSAGE = (
    "되돌리기는 이전 전에 만든 백업 파일로 taskflow.db 를 바꿔서 한다. "
    "(DATA-MIGRATION-PLAN.md 7절) 자동 다운그레이드는 사용자와 Task 를 잃을 수 있어 지원하지 않는다."
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(f"[M2 이전 중단] {message}")


def table_names(conn) -> set[str]:
    rows = conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type = 'table'")
    return {r[0] for r in rows}


def columns(conn, table: str) -> dict[str, tuple]:
    # 컬럼 이름 -> (type, notnull, pk)
    rows = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
    return {r[1]: (r[2], r[3], r[5]) for r in rows}


def snapshot(conn, table: str = "tasks") -> list[tuple]:
    # 건수가 아니라 id 와 값(title · description · status)까지 비교한다.
    return [
        tuple(r)
        for r in conn.exec_driver_sql(
            f"SELECT id, title, description, status FROM {table} ORDER BY id"
        )
    ]
