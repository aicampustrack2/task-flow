from fastapi import APIRouter, HTTPException

from app.db import connect
from app.rules import (
    RuleError,
    Status,
    validate_description,
    validate_status,
    validate_title,
)
from app.schemas import StatusChange, Task, TaskCreate, TaskUpdate

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


def _get_or_404(conn, task_id: int):
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="카드를 찾을 수 없습니다.")
    return row


@router.patch("/{task_id}", response_model=Task)
def update_task(task_id: int, body: TaskUpdate) -> Task:
    # 제목·설명만 고친다. 규칙은 등록과 같은 것을 쓴다. (D-006)
    conn = connect()
    try:
        row = _get_or_404(conn, task_id)
        title, description = row["title"], row["description"]
        try:
            if "title" in body.model_fields_set:
                title = validate_title(body.title)
            if "description" in body.model_fields_set:
                description = validate_description(body.description)
        except RuleError as e:
            raise HTTPException(status_code=422, detail=str(e)) from None
        with conn:
            conn.execute(
                "UPDATE tasks SET title = ?, description = ? WHERE id = ?",
                (title, description, task_id),
            )
        row = _get_or_404(conn, task_id)
    finally:
        conn.close()
    return _to_task(row)


@router.patch("/{task_id}/status", response_model=Task)
def change_status(task_id: int, body: StatusChange) -> Task:
    # 어느 상태에서 어느 상태로든 바꿀 수 있다. (D-007) 같은 상태로의 변경도 성공으로 본다.
    conn = connect()
    try:
        _get_or_404(conn, task_id)
        try:
            status = validate_status(body.status)
        except RuleError as e:
            raise HTTPException(status_code=422, detail=str(e)) from None
        with conn:
            conn.execute(
                "UPDATE tasks SET status = ? WHERE id = ?", (status.value, task_id)
            )
        row = _get_or_404(conn, task_id)
    finally:
        conn.close()
    return _to_task(row)


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: int) -> None:
    conn = connect()
    try:
        _get_or_404(conn, task_id)
        with conn:
            conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    finally:
        conn.close()
