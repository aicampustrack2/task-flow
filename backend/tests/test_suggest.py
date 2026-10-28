import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import anthropic
import httpx2 as httpx
from fastapi import HTTPException

from app.auth import current_user
from app.config import get_anthropic_api_key
from app.db import connect, init_db
from app.schemas import SuggestRequest, User
from app.suggest import MODEL, router, suggest

USER = User(id=1, username="me@test.com")


def reply(text: str, stop_reason: str = "end_turn"):
    block = SimpleNamespace(type="text", text=text)
    return SimpleNamespace(content=[block], stop_reason=stop_reason)


def api_error(cls, status: int):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls("error", response=httpx.Response(status, request=request), body=None)


GOOD = '{"priority": "HIGH", "due_date": "2026-10-29", "reason": "내일까지라 급하다"}'


class SuggestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_db = os.environ.get("TASKFLOW_DB")
        self._old_key = os.environ.get("ANTHROPIC_API_KEY")
        os.environ["TASKFLOW_DB"] = str(Path(self._tmp.name) / "test.db")
        os.environ["ANTHROPIC_API_KEY"] = "test-key-not-real"
        init_db()
        conn = connect()
        try:
            with conn:
                conn.execute("INSERT INTO users (username) VALUES ('me@test.com')")
                conn.execute(
                    "INSERT INTO tasks (title, description, status, owner_id, priority)"
                    " VALUES ('기존', '', 'TODO', 1, 'NORMAL')"
                )
        finally:
            conn.close()
        self.before = self.snapshot()
        self.create = MagicMock()
        client = SimpleNamespace(messages=SimpleNamespace(create=self.create))
        patcher = patch("app.suggest._client", return_value=client)
        self.client_factory = patcher.start()
        self.addCleanup(patcher.stop)
        today_patch = patch("app.suggest.today", return_value=date(2026, 10, 28))
        today_patch.start()
        self.addCleanup(today_patch.stop)

    def tearDown(self):
        for name, old in (("TASKFLOW_DB", self._old_db), ("ANTHROPIC_API_KEY", self._old_key)):
            if old is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = old
        self._tmp.cleanup()

    def snapshot(self):
        conn = connect()
        try:
            return [tuple(r) for r in conn.execute("SELECT * FROM tasks ORDER BY id")]
        finally:
            conn.close()

    def call(self, **kw):
        return suggest(SuggestRequest(**kw))

    def assertFails(self, status: int, detail: str | None = None, **kw):
        with self.assertRaises(HTTPException) as cm:
            self.call(title="내일까지 보고서", **kw)
        self.assertEqual(cm.exception.status_code, status)
        if detail is not None:
            self.assertEqual(cm.exception.detail, detail)
        self.assertEqual(self.snapshot(), self.before)  # 어느 경우에도 DB 는 그대로이다.


class SuggestSuccessTest(SuggestBase):
    def test_returns_suggestion_and_does_not_save(self):
        self.create.return_value = reply(GOOD)
        result = self.call(title="내일까지 보고서", description="급함")
        self.assertEqual(
            (result.priority, result.due_date, result.reason),
            ("HIGH", "2026-10-29", "내일까지라 급하다"),
        )
        self.assertEqual(self.snapshot(), self.before)

    def test_fenced_json_is_unwrapped(self):
        for text in (f"```json\n{GOOD}\n```", f"```\n{GOOD}\n```", f"  ```json\r\n{GOOD}\r\n```  "):
            self.create.return_value = reply(text)
            self.assertEqual(self.call(title="a").priority, "HIGH")

    def test_null_due_date_and_missing_keys_use_defaults(self):
        self.create.return_value = reply('{"priority": "LOW", "due_date": null, "reason": "r"}')
        self.assertIsNone(self.call(title="a").due_date)
        self.create.return_value = reply('{"reason": "단서 없음"}')
        result = self.call(title="a")
        self.assertEqual((result.priority, result.due_date), ("NORMAL", None))

    def test_call_arguments(self):
        self.create.return_value = reply(GOOD)
        self.call(title="  내일까지 보고서  ", description="설명")
        self.client_factory.assert_called_once_with("test-key-not-real")
        kw = self.create.call_args.kwargs
        self.assertEqual(kw["model"], MODEL)
        self.assertEqual(MODEL, "claude-haiku-5-5")
        self.assertEqual(kw["thinking"], {"type": "disabled"})
        content = kw["messages"][0]["content"]
        self.assertIn("2026-10-28", content)  # 오늘 날짜는 서버가 넣는다.
        self.assertIn("제목: 내일까지 보고서", content)
        self.assertIn("설명: 설명", content)
        for word in ("LOW", "NORMAL", "HIGH", "YYYY-MM-DD", "null"):
            self.assertIn(word, kw["system"])

    def test_braces_in_user_text_do_not_break_template(self):
        self.create.return_value = reply(GOOD)
        self.call(title="{today} {x}", description="}{")
        self.assertIn("제목: {today} {x}", self.create.call_args.kwargs["messages"][0]["content"])


class SuggestFailureTest(SuggestBase):
    def test_bad_values_are_502(self):
        for text in (
            '{"priority": "URGENT", "due_date": null, "reason": "r"}',
            '{"priority": null, "due_date": null, "reason": "r"}',
            '{"priority": "HIGH", "due_date": "내일", "reason": "r"}',
            '{"priority": "HIGH", "due_date": "2026-13-40", "reason": "r"}',
            '{"priority": "HIGH", "due_date": 20261029, "reason": "r"}',
            '{"priority": "HIGH", "due_date": null}',
            '{"priority": "HIGH", "due_date": null, "reason": 3}',
        ):
            with self.subTest(text=text):
                self.create.return_value = reply(text)
                self.assertFails(502, "제안 실패")

    def test_not_json_is_502(self):
        for text in ("그냥 문장입니다", '{"priority": "HIGH"', "[1, 2]", '"HIGH"', ""):
            with self.subTest(text=text):
                self.create.return_value = reply(text)
                self.assertFails(502, "제안 실패")

    def test_truncated_answer_is_502(self):
        self.create.return_value = reply(GOOD, stop_reason="max_tokens")
        self.assertFails(502, "제안 실패")

    def test_no_text_block_is_502(self):
        self.create.return_value = SimpleNamespace(content=[], stop_reason="end_turn")
        self.assertFails(502, "제안 실패")

    def test_missing_key_is_503_without_calling(self):
        del os.environ["ANTHROPIC_API_KEY"]
        with patch("app.config.ENV_PATH", Path(self._tmp.name) / "none.env"):
            self.assertFails(503, "AI 기능 꺼짐")
        self.create.assert_not_called()

    def test_rejected_key_is_503_off(self):
        self.create.side_effect = api_error(anthropic.AuthenticationError, 401)
        self.assertFails(503, "AI 기능 꺼짐")

    def test_rate_limit_busy_timeout_are_503(self):
        request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        for exc in (
            api_error(anthropic.RateLimitError, 429),
            api_error(anthropic.OverloadedError, 529),
            api_error(anthropic.ServiceUnavailableError, 503),
            anthropic.APITimeoutError(request=request),
            anthropic.APIConnectionError(request=request),
        ):
            with self.subTest(exc=type(exc).__name__):
                self.create.side_effect = exc
                with self.assertRaises(HTTPException) as cm:
                    self.call(title="a")
                self.assertEqual(cm.exception.status_code, 503)
                self.assertNotEqual(cm.exception.detail, "AI 기능 꺼짐")
                self.assertEqual(self.snapshot(), self.before)

    def test_other_api_error_is_502(self):
        self.create.side_effect = api_error(anthropic.BadRequestError, 400)
        self.assertFails(502, "제안 실패")

    def test_error_detail_does_not_leak_key(self):
        self.create.side_effect = api_error(anthropic.AuthenticationError, 401)
        with self.assertRaises(HTTPException) as cm:
            self.call(title="a")
        self.assertNotIn("test-key-not-real", str(cm.exception.detail))

    def test_input_rules_are_422_without_calling(self):
        for kw in ({"title": None}, {"title": "   "}, {"title": 3}, {"title": "a", "description": 5}):
            with self.subTest(kw=kw):
                with self.assertRaises(HTTPException) as cm:
                    self.call(**kw)
                self.assertEqual(cm.exception.status_code, 422)
        self.create.assert_not_called()


class SuggestRouteTest(unittest.TestCase):
    def test_login_required_and_route(self):
        self.assertIn(current_user, [d.dependency for d in router.dependencies])
        self.assertEqual(
            sorted((r.path, sorted(r.methods)[0]) for r in router.routes),
            [("/tasks/suggest", "POST")],
        )


class ApiKeyConfigTest(unittest.TestCase):
    def test_env_then_file_then_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp) / ".env"
            old = os.environ.pop("ANTHROPIC_API_KEY", None)
            try:
                self.assertIsNone(get_anthropic_api_key(env))
                env.write_text("ANTHROPIC_API_KEY=\n", encoding="utf-8")
                self.assertIsNone(get_anthropic_api_key(env))
                env.write_text("ANTHROPIC_API_KEY=from-file\n", encoding="utf-8")
                self.assertEqual(get_anthropic_api_key(env), "from-file")
                os.environ["ANTHROPIC_API_KEY"] = "from-env"
                self.assertEqual(get_anthropic_api_key(env), "from-env")
            finally:
                os.environ.pop("ANTHROPIC_API_KEY", None)
                if old is not None:
                    os.environ["ANTHROPIC_API_KEY"] = old


if __name__ == "__main__":
    unittest.main()
