import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.briefing import briefing
from app.db import connect, init_db
from app.schemas import User
from app.tasks import list_tasks

USER = User(id=1, username="me@test.com")

# 저장소는 값을 제한하지 않는다. (D-018) 예전 데이터나 손으로 고친 값으로 허용 밖의 값이 들어 있을 수 있다.
# 읽을 때 이런 행 하나 때문에 목록 전체가 오류가 나서는 안 된다.


class ReadInvalidStoredValuesTest(unittest.TestCase):
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
                rows = [
                    (1, "정상", "HIGH"),
                    (2, "허용 밖 우선순위", "URGENT"),  # 개발 DB 의 13번 행과 같은 경우
                    (3, "빈 우선순위", ""),
                    (4, "소문자", "high"),
                ]
                for task_id, title, priority in rows:
                    conn.execute(
                        "INSERT INTO tasks (id, title, description, status, owner_id, priority)"
                        " VALUES (?, ?, '', 'TODO', 1, ?)",
                        (task_id, title, priority),
                    )
        finally:
            conn.close()

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

    def test_list_tasks_survives_invalid_priority(self):
        before = self.snapshot()
        tasks = list_tasks(USER)
        self.assertEqual(sorted(t.id for t in tasks), [1, 2, 3, 4])  # 행을 숨기지 않는다.
        by_id = {t.id: t for t in tasks}
        self.assertEqual(by_id[1].priority, "HIGH")
        for task_id in (2, 3, 4):
            self.assertEqual(by_id[task_id].priority, "NORMAL")  # 읽을 때 보통으로 본다.
        self.assertEqual(self.snapshot(), before)  # 저장된 값은 고치지 않는다.

    def test_briefing_survives_invalid_priority(self):
        before = self.snapshot()
        create = MagicMock(
            return_value=SimpleNamespace(
                content=[SimpleNamespace(type="text", text='{"top3":[{"id":2,"reason":"r"}],"later":[],"cheer":"c"}')],
                stop_reason="end_turn",
            )
        )
        client = SimpleNamespace(messages=SimpleNamespace(create=create))
        with patch("app.ai_call._client", return_value=client), patch(
            "app.briefing.today", return_value=date(2026, 10, 29)
        ):
            result = briefing(USER)
        self.assertEqual([p.id for p in result.top3], [2])
        content = create.call_args.kwargs["messages"][0]["content"]
        self.assertIn("허용 밖 우선순위", content)  # 보내는 목록에 남아 있다.
        self.assertNotIn("URGENT", content)  # 허용 밖의 값은 모델에 보내지 않는다.
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
