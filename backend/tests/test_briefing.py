import json
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

from app.ai_call import MODEL
from app.auth import current_user
from app.briefing import SYSTEM_PROMPT, briefing, router
from app.db import connect, init_db
from app.schemas import User

USER = User(id=1, username="me@test.com")


def reply(text: str, stop_reason: str = "end_turn"):
    block = SimpleNamespace(type="text", text=text)
    return SimpleNamespace(content=[block], stop_reason=stop_reason)


def api_error(cls, status: int):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls("error", response=httpx.Response(status, request=request), body=None)


def answer(top3, later=(), cheer="힘내요"):
    return json.dumps({"top3": top3, "later": list(later), "cheer": cheer}, ensure_ascii=False)


class BriefingBase(unittest.TestCase):
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
                conn.execute("INSERT INTO users (username) VALUES ('other@test.com')")
                # id 1 지난 마감, 2 HIGH, 3 NORMAL, 4 LOW(완료 - 제외), 5 남의 것(제외), 6 진행 중
                rows = [
                    (1, "보고서 {x} \"끝\"", "비밀 설명", "TODO", 1, "HIGH", "2026-10-20"),
                    (2, "발표 준비", "", "TODO", 1, "HIGH", None),
                    (3, "청소", "", "TODO", 1, "NORMAL", "2026-11-05"),
                    (4, "끝난 일", "", "DONE", 1, "LOW", None),
                    (5, "남의 일", "", "TODO", 2, "HIGH", None),
                    (6, "진행 중인 일", "", "IN_PROGRESS", 1, "LOW", None),
                ]
                for r in rows:
                    conn.execute(
                        "INSERT INTO tasks (id, title, description, status, owner_id, priority,"
                        " due_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (r[0], r[1], r[2], r[3], r[4], r[5], r[6]),
                    )
        finally:
            conn.close()
        self.before = self.snapshot()
        self.create = MagicMock()
        client = SimpleNamespace(messages=SimpleNamespace(create=self.create))
        patcher = patch("app.ai_call._client", return_value=client)
        self.client_factory = patcher.start()
        self.addCleanup(patcher.stop)
        today_patch = patch("app.briefing.today", return_value=date(2026, 10, 28))
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

    def clear_tasks(self, where: str = "1=1"):
        conn = connect()
        try:
            with conn:
                conn.execute(f"DELETE FROM tasks WHERE {where}")
        finally:
            conn.close()
        self.before = self.snapshot()

    def sent(self) -> dict:
        # 모델에 실제로 보낸 내용에서 Task 목록(JSON)을 꺼낸다.
        content = self.create.call_args.kwargs["messages"][0]["content"]
        body = content.split("<tasks>\n", 1)[1].split("\n</tasks>", 1)[0]
        return {"tasks": json.loads(body), "content": content}

    def assertFails(self, status: int, detail: str | None = None):
        with self.assertRaises(HTTPException) as cm:
            briefing(USER)
        self.assertEqual(cm.exception.status_code, status)
        if detail is not None:
            self.assertEqual(cm.exception.detail, detail)
        self.assertEqual(self.snapshot(), self.before)  # 어느 경우에도 DB 는 그대로이다.


class BriefingSuccessTest(BriefingBase):
    def test_returns_briefing_and_does_not_save(self):
        self.create.return_value = reply(
            answer([{"id": 1, "reason": "마감 지남"}, {"id": 2, "reason": "HIGH"}], [3, 6], "화이팅")
        )
        result = briefing(USER)
        self.assertEqual([(p.id, p.reason) for p in result.top3], [(1, "마감 지남"), (2, "HIGH")])
        self.assertEqual((result.later, result.cheer), ([3, 6], "화이팅"))
        self.assertEqual(self.snapshot(), self.before)

    def test_sends_only_open_tasks_of_the_user_without_description(self):
        self.create.return_value = reply(answer([{"id": 1, "reason": "r"}]))
        briefing(USER)
        sent = self.sent()
        self.assertEqual([t["id"] for t in sent["tasks"]], [1, 2, 3, 6])  # 완료 · 남의 것 제외, 정렬됨
        for t in sent["tasks"]:
            self.assertEqual(set(t), {"id", "title", "priority", "due_date", "overdue"})
        self.assertEqual(
            sent["tasks"][0],
            {"id": 1, "title": "보고서 {x} \"끝\"", "priority": "HIGH", "due_date": "2026-10-20", "overdue": True},
        )
        self.assertFalse(sent["tasks"][2]["overdue"])
        self.assertNotIn("비밀 설명", sent["content"])
        self.assertIn("2026-10-28", sent["content"])  # 오늘 날짜는 서버가 넣는다.

    def test_call_arguments(self):
        self.create.return_value = reply(answer([{"id": 1, "reason": "r"}]))
        briefing(USER)
        self.client_factory.assert_called_once_with("test-key-not-real")
        kw = self.create.call_args.kwargs
        self.assertEqual((kw["model"], kw["thinking"]), (MODEL, {"type": "disabled"}))
        self.assertEqual(MODEL, "claude-haiku-5-5")
        self.assertEqual(kw["system"], SYSTEM_PROMPT)
        for word in ("top3", "later", "cheer", "한국어", "JSON"):
            self.assertIn(word, kw["system"])

    def test_fenced_json_is_unwrapped(self):
        good = answer([{"id": 2, "reason": "r"}])
        for text in (f"```json\n{good}\n```", f"```\n{good}\n```", f"  ```json\r\n{good}\r\n```  "):
            self.create.return_value = reply(text)
            self.assertEqual(briefing(USER).top3[0].id, 2)

    def test_missing_later_is_empty(self):
        self.create.return_value = reply('{"top3": [{"id": 2, "reason": "r"}], "cheer": "c"}')
        self.assertEqual(briefing(USER).later, [])


class BriefingCheckTest(BriefingBase):
    def test_unknown_ids_are_dropped(self):
        # 4 는 완료, 5 는 남의 것, 99 는 없는 것, "2" 는 문자열, True 는 bool 이다. 보낸 적 없다.
        picks = [{"id": i, "reason": "r"} for i in (4, 5, 99, "2", True, 2)]
        self.create.return_value = reply(answer(picks, [4, 5, 99, "3", True, 3]))
        result = briefing(USER)
        self.assertEqual([p.id for p in result.top3], [2])
        self.assertEqual(result.later, [3])

    def test_top3_keeps_first_three(self):
        picks = [{"id": i, "reason": f"r{i}"} for i in (1, 2, 3, 6)]
        self.create.return_value = reply(answer(picks))
        self.assertEqual([p.id for p in briefing(USER).top3], [1, 2, 3])

    def test_unknown_ids_do_not_use_up_the_three(self):
        picks = [{"id": i, "reason": "r"} for i in (99, 98, 1, 2, 3, 6)]
        self.create.return_value = reply(answer(picks))
        self.assertEqual([p.id for p in briefing(USER).top3], [1, 2, 3])

    def test_duplicates_and_overlap_are_removed(self):
        picks = [{"id": 1, "reason": "a"}, {"id": 1, "reason": "b"}, {"id": 2, "reason": "c"}]
        self.create.return_value = reply(answer(picks, [1, 3, 3, 6]))
        result = briefing(USER)
        self.assertEqual([(p.id, p.reason) for p in result.top3], [(1, "a"), (2, "c")])
        self.assertEqual(result.later, [3, 6])

    def test_all_top3_dropped_is_502(self):
        self.create.return_value = reply(answer([{"id": 99, "reason": "r"}], [1]))
        self.assertFails(502, "브리핑 실패")
        self.create.return_value = reply(answer([]))
        self.assertFails(502, "브리핑 실패")


class BriefingEmptyTest(BriefingBase):
    def assertEmpty(self):
        result = briefing(USER)
        self.assertEqual((result.top3, result.later), ([], []))
        self.assertEqual(result.cheer, "오늘은 비어 있어요")
        self.create.assert_not_called()
        self.assertEqual(self.snapshot(), self.before)

    def test_no_tasks_does_not_call_model(self):
        self.clear_tasks()
        self.assertEmpty()

    def test_only_done_or_others_tasks_is_empty(self):
        self.clear_tasks("status != 'DONE' AND owner_id = 1")  # 완료(4)와 남의 것(5)만 남는다.
        self.assertEqual(len(self.snapshot()), 2)
        self.assertEmpty()

    def test_empty_works_without_api_key(self):
        self.clear_tasks()
        del os.environ["ANTHROPIC_API_KEY"]
        with patch("app.config.ENV_PATH", Path(self._tmp.name) / "none.env"):
            self.assertEmpty()


class BriefingFailureTest(BriefingBase):
    def test_bad_shape_is_502(self):
        for text in (
            "그냥 문장입니다",
            '{"top3": [',
            "[1, 2]",
            '"top3"',
            '{"later": [1], "cheer": "c"}',
            '{"top3": {"id": 1}, "cheer": "c"}',
            '{"top3": ["1"], "cheer": "c"}',
            '{"top3": [{"id": 1}], "cheer": "c"}',
            '{"top3": [{"id": 1, "reason": 3}], "cheer": "c"}',
            '{"top3": [{"reason": "r"}], "cheer": "c"}',
            '{"top3": [{"id": 1, "reason": "r"}], "later": 3, "cheer": "c"}',
            '{"top3": [{"id": 1, "reason": "r"}]}',
            '{"top3": [{"id": 1, "reason": "r"}], "cheer": 5}',
        ):
            with self.subTest(text=text):
                self.create.return_value = reply(text)
                self.assertFails(502, "브리핑 실패")

    def test_truncated_and_empty_answers_are_502(self):
        self.create.return_value = reply(answer([{"id": 1, "reason": "r"}]), stop_reason="max_tokens")
        self.assertFails(502, "브리핑 실패")
        self.create.return_value = reply("  ")
        self.assertFails(502, "브리핑 실패")
        self.create.return_value = SimpleNamespace(content=[], stop_reason="end_turn")
        self.assertFails(502, "브리핑 실패")

    def test_other_api_error_is_502(self):
        self.create.side_effect = api_error(anthropic.BadRequestError, 400)
        self.assertFails(502, "브리핑 실패")

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
                    briefing(USER)
                self.assertEqual(cm.exception.status_code, 503)
                self.assertNotEqual(cm.exception.detail, "AI 기능 꺼짐")
                self.assertEqual(self.snapshot(), self.before)

    def test_error_detail_does_not_leak_key(self):
        self.create.side_effect = api_error(anthropic.AuthenticationError, 401)
        with self.assertRaises(HTTPException) as cm:
            briefing(USER)
        self.assertNotIn("test-key-not-real", str(cm.exception.detail))


class BriefingRouteTest(unittest.TestCase):
    def test_login_required_and_route(self):
        self.assertIn(current_user, [d.dependency for d in router.dependencies])
        self.assertEqual(
            sorted((r.path, sorted(r.methods)[0]) for r in router.routes),
            [("/tasks/briefing", "POST")],
        )

    def test_no_request_body_and_response_shape(self):
        from app.main import app

        spec = app.openapi()
        op = spec["paths"]["/tasks/briefing"]["post"]
        self.assertNotIn("requestBody", op)
        self.assertEqual(
            list(spec["components"]["schemas"]["Briefing"]["properties"]), ["top3", "later", "cheer"]
        )


if __name__ == "__main__":
    unittest.main()
