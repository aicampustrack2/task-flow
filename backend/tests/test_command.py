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
from app.command import SYSTEM_PROMPT, command, router
from app.db import connect, init_db
from app.rules import COMMAND_MAX_LENGTH
from app.schemas import CommandRequest, User

USER = User(id=1, username="me@test.com")
NOT_UNDERSTOOD = "무슨 일을 할지 알아듣지 못했어요. 다시 말해 주세요."


def reply(text: str, stop_reason: str = "end_turn"):
    block = SimpleNamespace(type="text", text=text)
    return SimpleNamespace(content=[block], stop_reason=stop_reason)


def api_error(cls, status: int):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls("error", response=httpx.Response(status, request=request), body=None)


def act(kind, id=None, title=None, priority=None, due_date=None):
    return {"kind": kind, "id": id, "title": title, "priority": priority, "due_date": due_date}


def answer(actions, ask=None):
    return json.dumps({"actions": actions, "ask": ask}, ensure_ascii=False)


class CommandBase(unittest.TestCase):
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
                # id 1 지난 마감, 2 HIGH, 3 진행 중, 4 완료(제외), 5 남의 것(제외)
                rows = [
                    (1, "보고서 {x} \"끝\"", "비밀 설명", "TODO", 1, "HIGH", "2026-10-20"),
                    (2, "발표 준비", "", "TODO", 1, "HIGH", None),
                    (3, "청소", "", "IN_PROGRESS", 1, "NORMAL", "2026-11-05"),
                    (4, "끝난 일", "", "DONE", 1, "LOW", None),
                    (5, "남의 일", "", "TODO", 2, "HIGH", None),
                ]
                for r in rows:
                    conn.execute(
                        "INSERT INTO tasks (id, title, description, status, owner_id, priority,"
                        " due_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        r,
                    )
        finally:
            conn.close()
        self.before = self.snapshot()
        self.create = MagicMock()
        client = SimpleNamespace(messages=SimpleNamespace(create=self.create))
        patcher = patch("app.ai_call._client", return_value=client)
        patcher.start()
        self.addCleanup(patcher.stop)
        today_patch = patch("app.command.today", return_value=date(2026, 10, 28))
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

    def run_cmd(self, text="내일까지 발표 준비"):
        return command(CommandRequest(text=text), USER)

    def sent(self) -> dict:
        content = self.create.call_args.kwargs["messages"][0]["content"]
        body = content.split("<tasks>\n", 1)[1].split("\n</tasks>", 1)[0]
        return {"tasks": json.loads(body), "content": content}

    def assertFails(self, status: int, detail: str | None = None, text="할 일"):
        with self.assertRaises(HTTPException) as cm:
            self.run_cmd(text)
        self.assertEqual(cm.exception.status_code, status)
        if detail is not None:
            self.assertEqual(cm.exception.detail, detail)
        self.assertEqual(self.snapshot(), self.before)  # 어느 경우에도 DB 는 그대로이다.
        return cm.exception


class CommandInputTest(CommandBase):
    def test_empty_blank_and_non_string_are_422_without_calling(self):
        for bad in ["", "   \t\n", None, 3]:
            with self.subTest(bad=bad):
                self.assertFails(422, "명령은 비워 둘 수 없습니다.", text=bad)
        self.create.assert_not_called()

    def test_length_limit_is_200(self):
        self.create.return_value = reply(answer([act("done", 2)]))
        self.run_cmd("가" * COMMAND_MAX_LENGTH)
        self.assertFails(422, f"명령은 {COMMAND_MAX_LENGTH}자 이하여야 합니다.", text="가" * 201)

    def test_length_counts_after_trimming(self):
        self.create.return_value = reply(answer([act("done", 2)]))
        self.run_cmd("  " + "가" * 200 + "  ")

    def test_422_comes_before_503(self):
        with patch("app.ai_call.get_anthropic_api_key", return_value=None):
            self.assertFails(422, text="")


class CommandSuccessTest(CommandBase):
    def test_returns_actions_and_does_not_save(self):
        self.create.return_value = reply(
            answer(
                [
                    act("add", title="  우유 사기 ", priority="HIGH", due_date="2026-10-29"),
                    act("due", 2, due_date="2026-10-30"),
                    act("done", 3),
                ]
            )
        )
        result = self.run_cmd()
        self.assertEqual(
            [a.model_dump() for a in result.actions],
            [
                act("add", title="우유 사기", priority="HIGH", due_date="2026-10-29"),
                act("due", 2, due_date="2026-10-30"),
                act("done", 3),
            ],
        )
        self.assertIsNone(result.ask)
        self.assertEqual(self.snapshot(), self.before)

    def test_add_defaults_priority_normal_and_no_due_date(self):
        self.create.return_value = reply(answer([{"kind": "add", "title": "빨래"}]))
        a = self.run_cmd().actions[0]
        self.assertEqual((a.kind, a.id, a.title, a.priority, a.due_date), ("add", None, "빨래", "NORMAL", None))

    def test_extra_fields_are_not_kept(self):
        self.create.return_value = reply(
            answer([act("done", 2, title="무시", priority="HIGH", due_date="2026-10-30")])
        )
        self.assertEqual(self.run_cmd().actions[0].model_dump(), act("done", 2))

    def test_sends_only_open_tasks_of_the_user_without_description(self):
        self.create.return_value = reply(answer([act("done", 2)]))
        sentence = '보고서 끝내고 "청소" 완료'
        self.run_cmd(sentence)
        sent = self.sent()
        self.assertEqual([t["id"] for t in sent["tasks"]], [1, 2, 3])  # 완료 · 남의 것 제외
        for t in sent["tasks"]:
            self.assertEqual(set(t), {"id", "title", "priority", "due_date"})
        self.assertNotIn("비밀 설명", sent["content"])
        self.assertIn("2026-10-28", sent["content"])
        self.assertIn(json.dumps(sentence, ensure_ascii=False), sent["content"])

    def test_call_arguments(self):
        self.create.return_value = reply(answer([act("done", 2)]))
        self.run_cmd()
        kw = self.create.call_args.kwargs
        self.assertEqual(kw["model"], MODEL)
        self.assertEqual(kw["system"], SYSTEM_PROMPT)
        self.assertEqual(kw["thinking"], {"type": "disabled"})

    def test_no_tasks_still_calls_model(self):
        conn = connect()
        try:
            with conn:
                conn.execute("DELETE FROM tasks")
        finally:
            conn.close()
        self.before = self.snapshot()
        self.create.return_value = reply(answer([act("add", title="새 일")]))
        self.assertEqual(self.run_cmd().actions[0].title, "새 일")
        self.assertEqual(self.sent()["tasks"], [])

    def test_fenced_json_is_unwrapped(self):
        self.create.return_value = reply("```json\n" + answer([act("done", 2)]) + "\n```")
        self.assertEqual(self.run_cmd().actions[0].id, 2)


class CommandCheckTest(CommandBase):
    def check(self, actions, ask=None):
        self.create.return_value = reply(answer(actions, ask))
        return self.run_cmd()

    def test_unknown_done_and_other_users_ids_are_dropped(self):
        # 99 는 없는 id, 4 는 완료, 5 는 남의 것이다. 보낸 적 없는 id 이다.
        r = self.check([act("done", 99), act("done", 4), act("done", 5), act("done", 2)])
        self.assertEqual([a.id for a in r.actions], [2])

    def test_unknown_due_id_is_dropped(self):
        r = self.check([act("due", 99, due_date="2026-11-01"), act("due", 5, due_date="2026-11-01")])
        self.assertEqual(r.actions, [])

    def test_bad_id_types_are_dropped(self):
        r = self.check(
            [act("done", "2"), act("done", True), act("done", 2.5), act("done", None), act("done", 1)]
        )
        self.assertEqual([a.id for a in r.actions], [1])

    def test_out_of_rule_dates_are_dropped(self):
        r = self.check(
            [
                act("due", 2, due_date="2026-02-30"),
                act("due", 2, due_date="내일"),
                act("due", 2, due_date="2026-1-5"),
                act("due", 2, due_date=None),
                act("due", 2, due_date=20261030),
                act("add", title="x", due_date="2026-13-01"),
                act("due", 3, due_date="2026-11-01"),
            ]
        )
        self.assertEqual([(a.kind, a.id, a.due_date) for a in r.actions], [("due", 3, "2026-11-01")])

    def test_bad_add_values_are_dropped(self):
        r = self.check(
            [
                act("add", title="  "),
                act("add", title=None),
                act("add", title="x", priority="URGENT"),
                act("add", title="x", priority=3),
                act("add", title="ok"),
            ]
        )
        self.assertEqual([(a.title, a.priority) for a in r.actions], [("ok", "NORMAL")])

    def test_unknown_kind_and_non_objects_are_dropped(self):
        r = self.check([act("delete", 2), "done", 3, None, act("done", 2)])
        self.assertEqual([(a.kind, a.id) for a in r.actions], [("done", 2)])

    def test_duplicates_keep_first(self):
        r = self.check(
            [
                act("done", 2),
                act("done", 2),
                act("due", 2, due_date="2026-11-01"),
                act("due", 2, due_date="2026-11-02"),
            ]
        )
        self.assertEqual(
            [(a.kind, a.due_date) for a in r.actions], [("done", None), ("due", "2026-11-01")]
        )

    def test_nothing_left_uses_models_ask(self):
        r = self.check([act("done", 99)], ask="어느 카드를 말씀하시나요?")
        self.assertEqual((r.actions, r.ask), ([], "어느 카드를 말씀하시나요?"))

    def test_nothing_left_without_ask_uses_fixed_sentence(self):
        for ask in (None, "", "  "):
            with self.subTest(ask=ask):
                r = self.check([], ask=ask)
                self.assertEqual((r.actions, r.ask), ([], NOT_UNDERSTOOD))

    def test_models_ask_is_ignored_when_actions_remain(self):
        r = self.check([act("done", 2)], ask="뭐라고요?")
        self.assertIsNone(r.ask)


class CommandFailureTest(CommandBase):
    def test_bad_shape_is_502(self):
        bad = [
            "그냥 글",
            "[]",
            "3",
            json.dumps({"ask": None}),
            json.dumps({"actions": {}, "ask": None}),
            json.dumps({"actions": [], "ask": 3}),
            json.dumps({"actions": [], "ask": ["a"]}),
        ]
        for text in bad:
            with self.subTest(text=text):
                self.create.return_value = reply(text)
                self.assertFails(502, "명령 실패")

    def test_truncated_and_empty_answers_are_502(self):
        self.create.return_value = reply(answer([act("done", 2)]), stop_reason="max_tokens")
        self.assertFails(502, "명령 실패")
        self.create.return_value = reply("  ")
        self.assertFails(502, "명령 실패")

    def test_other_api_error_is_502(self):
        self.create.side_effect = api_error(anthropic.BadRequestError, 400)
        self.assertFails(502, "명령 실패")

    def test_missing_key_is_503_without_calling(self):
        with patch("app.ai_call.get_anthropic_api_key", return_value=None):
            self.assertFails(503, "AI 기능 꺼짐")
        self.create.assert_not_called()

    def test_rejected_key_is_503_off(self):
        self.create.side_effect = api_error(anthropic.AuthenticationError, 401)
        self.assertFails(503, "AI 기능 꺼짐")

    def test_rate_limit_busy_timeout_are_503(self):
        req = httpx.Request("POST", "https://api.anthropic.com")
        errors = [
            api_error(anthropic.RateLimitError, 429),
            api_error(anthropic.InternalServerError, 500),
            api_error(anthropic.ServiceUnavailableError, 503),
            anthropic.APIConnectionError(request=req),
            anthropic.APITimeoutError(request=req),
        ]
        for err in errors:
            with self.subTest(err=type(err).__name__):
                self.create.side_effect = err
                e = self.assertFails(503)
                self.assertNotIn("test-key-not-real", str(e.detail))


class CommandRouteTest(unittest.TestCase):
    def test_login_required_and_route(self):
        self.assertIn(current_user, [d.dependency for d in router.dependencies])
        self.assertEqual(
            sorted((r.path, sorted(r.methods)[0]) for r in router.routes),
            [("/tasks/command", "POST")],
        )

    def test_request_and_response_shape(self):
        from app.main import app

        schemas = app.openapi()["components"]["schemas"]
        self.assertEqual(list(schemas["CommandRequest"]["properties"]), ["text"])
        self.assertEqual(list(schemas["CommandResult"]["properties"]), ["actions", "ask"])
        self.assertEqual(
            list(schemas["CommandAction"]["properties"]),
            ["kind", "id", "title", "priority", "due_date"],
        )


if __name__ == "__main__":
    unittest.main()
