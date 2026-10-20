from fastapi import APIRouter, HTTPException

from app.db import connect
from app.rules import RuleError, Status, validate_description, validate_title
from app.schemas import Task, TaskCreate

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _to_task(row) -> Task:
    return Task(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        status=row["status"],
    )


@router.get("", response_model=list[Task])
def list_tasks() -> list[Task]:
    # 읽기에 실패하면 예외가 그대로 오류 응답이 된다. 빈 목록으로 응답하지 않는다.
    conn = connect()
    try:
        rows = conn.execute("SELECT * FROM tasks ORDER BY id").fetchall()
    finally:
        conn.close()
    return [_to_task(r) for r in rows]


@router.post("", response_model=Task, status_code=201)
def create_task(body: TaskCreate) -> Task:
    try:
        title = validate_title(body.title)
        description = validate_description(body.description)
    except RuleError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None

    # 저장(commit)이 끝난 뒤에만 응답한다. (D-004) 새 카드의 처음 상태는 TODO.
    conn = connect()
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO tasks (title, description, status) VALUES (?, ?, ?)",
                (title, description, Status.TODO.value),
            )
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)).fetchone()
    finally:
        conn.close()
    return _to_task(row)
