from typing import Any

from pydantic import BaseModel

from app.rules import Status


class TaskCreate(BaseModel):
    # 값 검사는 rules.py 한 곳에서 한다. (D-006) 여기서는 받기만 한다.
    title: Any = None
    description: Any = None


class Task(BaseModel):
    id: int
    title: str
    description: str
    status: Status
