import re

import anthropic
from fastapi import HTTPException

from app.config import get_anthropic_api_key

# 모델 한 번 부르기. 키 확인, 호출, 오류 → 503/502 변환, 코드 블록 표시 벗기기까지 맡는다.
# 호출하는 쪽은 돌려받은 글을 JSON 으로 읽고 값을 검사하기만 하면 된다.
MODEL = "claude-haiku-5-5"

_FENCE = re.compile(r"```[A-Za-z0-9_-]*[ \t]*\r?\n?(.*?)\r?\n?```", re.DOTALL)

_OFF = "AI 기능 꺼짐"
_BUSY = "지금은 AI 기능을 쓸 수 없습니다. 잠시 뒤 다시 시도해 주세요."


def _client(api_key: str) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=api_key, timeout=30.0, max_retries=1)


def _strip_fence(text: str) -> str:
    # 앞뒤에 ``` 표시가 붙어 오면 안의 내용만 꺼낸다.
    text = text.strip()
    m = _FENCE.fullmatch(text)
    return m.group(1).strip() if m else text


def call_model(system: str, content: str, max_tokens: int, failed: str) -> str:
    # 키 없음·거부, 한도·과부하·연결·시간 초과는 503, 그 밖의 오류와 잘린 답·빈 답은 502(detail=failed)이다.
    api_key = get_anthropic_api_key()
    if api_key is None:
        raise HTTPException(status_code=503, detail=_OFF)
    try:
        message = _client(api_key).messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            thinking={"type": "disabled"},
            system=system,
            messages=[{"role": "user", "content": content}],
        )
    except (anthropic.AuthenticationError, anthropic.PermissionDeniedError):
        # 키가 거부되었다. 키 값은 오류에 담지 않는다.
        raise HTTPException(status_code=503, detail=_OFF) from None
    except (
        anthropic.RateLimitError,
        anthropic.OverloadedError,
        anthropic.ServiceUnavailableError,
        anthropic.InternalServerError,
        anthropic.APIConnectionError,  # 시간 초과(APITimeoutError)도 포함한다.
    ):
        raise HTTPException(status_code=503, detail=_BUSY) from None
    except anthropic.APIError:
        raise HTTPException(status_code=502, detail=failed) from None
    if message.stop_reason == "max_tokens":
        raise HTTPException(status_code=502, detail=failed)
    text = "".join(b.text for b in message.content if getattr(b, "type", None) == "text")
    if not text.strip():
        raise HTTPException(status_code=502, detail=failed)
    return _strip_fence(text)
