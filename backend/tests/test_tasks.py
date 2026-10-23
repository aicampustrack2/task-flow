import os
import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

from app.auth import current_user
from app.db import connect, init_db
from app.schemas import StatusChange, TaskCreate, TaskUpdate, User
from app.tasks import (
    change_status,
    create_task,
    delete_task,
    list_tasks,
    router,
    update_task,
)


def add_user(name: str) -> User:
    conn = connect()
    try:
        with conn:
            uid = conn.execute("INSERT INTO users (username) VALUES (?)", (name,)).lastrowid
    finally:
        conn.close()
    return User(id=uid, username=name)


class TasksBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old = os.environ.get("TASKFLOW_DB")
        os.environ["TASKFLOW_DB"] = str(Path(self._tmp.name) / "test.db")
        init_db()
        self.me = add_user("me@test.com")

    def tearDown(self):
        if self._old is None:
            del os.environ["TASKFLOW_DB"]
        else:
            os.environ["TASKFLOW_DB"] = self._old
        self._tmp.cleanup()

    # 핸들러를 직접 부르므로 로그인한 사용자를 user 로 넘긴다.
    def create(self, **kw):
        return create_task(TaskCreate(**kw), user=self.me)

    def list(self):
        return list_tasks(user=self.me)


class TasksApiTest(TasksBase):
    def test_empty_list_is_success(self):
        self.assertEqual(self.list(), [])

    def test_create_starts_as_todo_and_description_optional(self):
        task = self.create(title="  첫 카드 ")
        self.assertEqual(task.title, "첫 카드")
        self.assertEqual(task.description, "")
        self.assertEqual(task.status, "TODO")

    def test_list_in_id_order(self):
        self.create(title="a", description="x")
        self.create(title="b")
        self.assertEqual([t.title for t in self.list()], ["a", "b"])

    def test_blank_title_rejected_and_not_saved(self):
        for bad in [None, "", "   "]:
            with self.subTest(bad=bad):
                with self.assertRaises(HTTPException) as cm:
                    self.create(title=bad)
                self.assertEqual(cm.exception.status_code, 422)
        self.assertEqual(self.list(), [])


class TaskChangeTest(TasksApiTest):
    def _code(self, fn, *args, **kw):
        with self.assertRaises(HTTPException) as cm:
            fn(*args, user=self.me, **kw)
        return cm.exception.status_code

    def test_every_status_transition(self):
        states = ["TODO", "IN_PROGRESS", "DONE"]
        for src in states:
            for dst in states:
                with self.subTest(src=src, dst=dst):
                    t = self.create(title="x")
                    change_status(t.id, StatusChange(status=src), user=self.me)
                    self.assertEqual(
                        change_status(t.id, StatusChange(status=dst), user=self.me).status, dst
                    )
                    self.assertEqual([x.status for x in self.list() if x.id == t.id], [dst])

    def test_invalid_status_rejected_and_unchanged(self):
        t = self.create(title="x")
        for bad in [None, "", "done", "DOING"]:
            with self.subTest(bad=bad):
                self.assertEqual(self._code(change_status, t.id, StatusChange(status=bad)), 422)
        self.assertEqual(self.list()[0].status, "TODO")

    def test_update_title_and_description_keeps_status(self):
        t = self.create(title="a", description="d")
        change_status(t.id, StatusChange(status="DONE"), user=self.me)
        u = update_task(t.id, TaskUpdate(title=" b ", description="e"), user=self.me)
        self.assertEqual((u.title, u.description, u.status), ("b", "e", "DONE"))

    def test_update_only_sent_fields(self):
        t = self.create(title="a", description="d")
        self.assertEqual(update_task(t.id, TaskUpdate(description="e"), user=self.me).title, "a")
        self.assertEqual(update_task(t.id, TaskUpdate(title="b"), user=self.me).description, "e")

    def test_update_blank_title_rejected_and_unchanged(self):
        t = self.create(title="a", description="d")
        for bad in [None, "", "  "]:
            with self.subTest(bad=bad):
                self.assertEqual(self._code(update_task, t.id, TaskUpdate(title=bad)), 422)
        self.assertEqual((self.list()[0].title, self.list()[0].description), ("a", "d"))

    def test_missing_card_rejected(self):
        self.assertEqual(self._code(update_task, 999, TaskUpdate(title="x")), 404)
        self.assertEqual(self._code(change_status, 999, StatusChange(status="DONE")), 404)
        self.assertEqual(self._code(delete_task, 999), 404)

    def test_delete_removes_card(self):
        a = self.create(title="a")
        b = self.create(title="b")
        delete_task(a.id, user=self.me)
        self.assertEqual([t.id for t in self.list()], [b.id])
        self.assertEqual(self._code(delete_task, a.id), 404)


class OwnershipTest(TasksBase):
    # R-008: 로그인한 사람은 자기 Task만 보고 바꾼다. 남의 Task는 없는 Task와 같은 404이다.
    def setUp(self):
        super().setUp()
        self.other = add_user("other@test.com")
        self.mine = self.create(title="내 것", description="d")
        self.theirs = create_task(TaskCreate(title="남의 것", description="d"), user=self.other)

    def _error(self, fn, *args):
        with self.assertRaises(HTTPException) as cm:
            fn(*args, user=self.me)
        return cm.exception

    def _snapshot(self):
        conn = connect()
        try:
            return [tuple(r) for r in conn.execute("SELECT * FROM tasks ORDER BY id")]
        finally:
            conn.close()

    def test_list_shows_only_own_tasks(self):
        self.assertEqual([t.id for t in self.list()], [self.mine.id])
        self.assertEqual([t.id for t in list_tasks(user=self.other)], [self.theirs.id])

    def test_new_task_belongs_to_logged_in_user(self):
        conn = connect()
        owner = conn.execute("SELECT owner_id FROM tasks WHERE id = ?", (self.mine.id,)).fetchone()[0]
        conn.close()
        self.assertEqual(owner, self.me.id)

    def test_request_cannot_choose_owner(self):
        # 본문에 owner_id 를 실어도 무시하고 로그인한 사용자가 소유자가 된다.
        body = TaskCreate.model_validate({"title": "x", "owner_id": self.other.id})
        task = create_task(body, user=self.me)
        self.assertEqual([t.id for t in list_tasks(user=self.me)][-1], task.id)
        self.assertNotIn(task.id, [t.id for t in list_tasks(user=self.other)])

    def test_other_users_task_is_404_for_update_status_delete_and_unchanged(self):
        before = self._snapshot()
        errors = [
            self._error(update_task, self.theirs.id, TaskUpdate(title="해킹")),
            self._error(change_status, self.theirs.id, StatusChange(status="DONE")),
            self._error(delete_task, self.theirs.id),
        ]
        self.assertEqual([e.status_code for e in errors], [404, 404, 404])
        self.assertEqual(self._snapshot(), before)

    def test_other_users_task_looks_the_same_as_missing(self):
        theirs = self._error(update_task, self.theirs.id, TaskUpdate(title="x"))
        missing = self._error(update_task, 9999, TaskUpdate(title="x"))
        self.assertEqual((theirs.status_code, theirs.detail), (missing.status_code, missing.detail))

    def test_invalid_input_on_other_users_task_is_404_not_422(self):
        # 남의 Task가 있는지 알려 주지 않는다.
        self.assertEqual(self._error(update_task, self.theirs.id, TaskUpdate(title="")).status_code, 404)
        self.assertEqual(
            self._error(change_status, self.theirs.id, StatusChange(status="x")).status_code, 404
        )


class ProtectionTest(unittest.TestCase):
    def test_every_route_requires_login(self):
        # 라우터 전체에 걸린 로그인 확인이 있다. 이 라우터에 더하는 API도 기본으로 보호된다.
        self.assertIn(current_user, [d.dependency for d in router.dependencies])
        self.assertEqual(
            sorted((r.path, sorted(r.methods)[0]) for r in router.routes),
            sorted(
                [
                    ("/tasks", "GET"),
                    ("/tasks", "POST"),
                    ("/tasks/{task_id}", "PATCH"),
                    ("/tasks/{task_id}/status", "PATCH"),
                    ("/tasks/{task_id}", "DELETE"),
                ]
            ),
        )


if __name__ == "__main__":
    unittest.main()
