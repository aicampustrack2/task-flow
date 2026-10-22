from fastapi import APIRouter, Depends, HTTPException

from app.auth import current_user
from app.db import connect
from app.rules import (
    RuleError,
    Status,
    validate_description,
    validate_status,
    validate_title,
)
from app.schemas import StatusChange, Task, TaskCreate, TaskUpdate, User

# 모든 Task API는 로그인이 필요하다(401). 로그인한 사용자는 자기 Task만 보고 바꾼다. (R-008)
# 소유자는 서버가 로그인한 사용자로 정하고, 요청 본문의 owner 값은 받지 않는다.
router = APIRouter(prefix="/tasks", tags=["tasks"], dependencies=[Depends(current_user)])


def _to_task(row) -> Task:
    return Task(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        status=row["status"],
    )


@router.get("", response_model=list[Task])
def list_tasks(user: User = Depends(current_user)) -> list[Task]:
    # 읽기에 실패하면 예외가 그대로 오류 응답이 된다. 빈 목록으로 응답하지 않는다.
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE owner_id = ? ORDER BY id", (user.id,)
        ).fetchall()
    finally:
        conn.close()
    return [_to_task(r) for r in rows]


@router.post("", response_model=Task, status_code=201)
def create_task(body: TaskCreate, user: User = Depends(current_user)) -> Task:
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
                "INSERT INTO tasks (title, description, status, owner_id) VALUES (?, ?, ?, ?)",
                (title, description, Status.TODO.value, user.id),
            )
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)).fetchone()
    finally:
        conn.close()
    return _to_task(row)


def _get_or_404(conn, task_id: int, owner_id: int):
    # 소유자 확인은 조회 조건에서 한다. 남의 Task와 없는 Task는 같은 404이다.
    row = conn.execute(
        "SELECT * FROM tasks WHERE id = ? AND owner_id = ?", (task_id, owner_id)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="카드를 찾을 수 없습니다.")
    return row


@router.patch("/{task_id}", response_model=Task)
def update_task(task_id: int, body: TaskUpdate, user: User = Depends(current_user)) -> Task:
    # 제목·설명만 고친다. 규칙은 등록과 같은 것을 쓴다. (D-006)
    conn = connect()
    try:
        row = _get_or_404(conn, task_id, user.id)
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
                "UPDATE tasks SET title = ?, description = ? WHERE id = ? AND owner_id = ?",
                (title, description, task_id, user.id),
            )
        row = _get_or_404(conn, task_id, user.id)
    finally:
        conn.close()
    return _to_task(row)


@router.patch("/{task_id}/status", response_model=Task)
def change_status(
    task_id: int, body: StatusChange, user: User = Depends(current_user)
) -> Task:
    # 어느 상태에서 어느 상태로든 바꿀 수 있다. (D-007) 같은 상태로의 변경도 성공으로 본다.
    conn = connect()
    try:
        _get_or_404(conn, task_id, user.id)
        try:
            status = validate_status(body.status)
        except RuleError as e:
            raise HTTPException(status_code=422, detail=str(e)) from None
        with conn:
            conn.execute(
                "UPDATE tasks SET status = ? WHERE id = ? AND owner_id = ?",
                (status.value, task_id, user.id),
            )
        row = _get_or_404(conn, task_id, user.id)
    finally:
        conn.close()
    return _to_task(row)


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: int, user: User = Depends(current_user)) -> None:
    conn = connect()
    try:
        _get_or_404(conn, task_id, user.id)
        with conn:
            conn.execute(
                "DELETE FROM tasks WHERE id = ? AND owner_id = ?", (task_id, user.id)
            )
    finally:
        conn.close()
