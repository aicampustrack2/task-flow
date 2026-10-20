from enum import StrEnum


class Status(StrEnum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"


class RuleError(ValueError):
    """제목·상태 규칙 위반 (API-SPEC 2절의 제목 규칙 위반, 상태 값 위반)."""


# 카드 규칙은 한 곳에 두고 등록과 수정이 함께 쓴다. (D-006)
def validate_title(title: object) -> str:
    # 필수이고 공백만 있으면 거부한다. 저장할 때 앞뒤 공백은 지운다. (D-009, D-010)
    if not isinstance(title, str) or not title.strip():
        raise RuleError("제목은 비워 둘 수 없습니다.")
    return title.strip()


def validate_description(description: object) -> str:
    # 선택이다. 없으면 빈 문자열로 저장한다. (D-011)
    if description is None:
        return ""
    if not isinstance(description, str):
        raise RuleError("설명은 문자열이어야 합니다.")
    return description


def validate_status(status: object) -> Status:
    try:
        return Status(status)
    except ValueError:
        raise RuleError("상태는 TODO, IN_PROGRESS, DONE 중 하나여야 합니다.") from None
