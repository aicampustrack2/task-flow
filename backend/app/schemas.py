from typing import Any, Literal

from pydantic import BaseModel

from app.rules import Priority, Status


class TaskCreate(BaseModel):
    # 값 검사는 rules.py 한 곳에서 한다. (D-006) 여기서는 받기만 한다.
    # priority · due_date 는 보내지 않으면 NORMAL · 없음이다. (model_fields_set 으로 생략과 null 을 구분한다)
    title: Any = None
    description: Any = None
    priority: Any = None
    due_date: Any = None


class TaskUpdate(BaseModel):
    # 보낸 필드만 고친다. 상태는 받지 않는다. (상태 변경은 별도 요청)
    title: Any = None
    description: Any = None
    priority: Any = None
    due_date: Any = None


class StatusChange(BaseModel):
    status: Any = None


class Task(BaseModel):
    id: int
    title: str
    description: str
    status: Status
    priority: Priority
    due_date: str | None
    # 저장하는 값이 아니라 응답을 줄 때 서버가 계산한다. (R-011)
    is_overdue: bool


class SuggestRequest(BaseModel):
    # 값 검사는 rules.py 한 곳에서 한다. 여기서는 받기만 한다.
    title: Any = None
    description: Any = None


class Suggestion(BaseModel):
    # 제안만 돌려준다. 저장하지 않는다.
    priority: Priority
    due_date: str | None
    reason: str


class BriefingPick(BaseModel):
    id: int
    reason: str


class Briefing(BaseModel):
    # 오늘 브리핑. 돌려주기만 하고 저장하지 않는다. top3 는 먼저 할 일(최대 셋), later 는 미뤄도 되는 Task id.
    top3: list[BriefingPick]
    later: list[int]
    cheer: str


class CommandRequest(BaseModel):
    # 값 검사는 rules.py 한 곳에서 한다. 여기서는 받기만 한다.
    text: Any = None


class CommandAction(BaseModel):
    # 제안 하나. add 는 title · priority · due_date, due 는 id · due_date, done 은 id 만 쓰고 나머지는 null.
    kind: Literal["add", "due", "done"]
    id: int | None
    title: str | None
    priority: Priority | None
    due_date: str | None


class CommandResult(BaseModel):
    # 제안만 돌려준다. 저장하지 않는다. 쓸 수 있는 action 이 없을 때만 ask 가 문장이다.
    actions: list[CommandAction]
    ask: str | None


class Credentials(BaseModel):
    # 값 검사는 rules.py 한 곳에서 한다. 여기서는 받기만 한다.
    username: Any = None
    password: Any = None


class User(BaseModel):
    # 응답에는 비밀번호와 해시를 담지 않는다.
    id: int
    username: str
