import os
import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

from app.db import init_db
from app.schemas import StatusChange, TaskCreate, TaskUpdate
from app.tasks import change_status, create_task, delete_task, list_tasks, update_task


class TasksApiTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old = os.environ.get("TASKFLOW_DB")
        os.environ["TASKFLOW_DB"] = str(Path(self._tmp.name) / "test.db")
        init_db()

    def tearDown(self):
        if self._old is None:
            del os.environ["TASKFLOW_DB"]
        else:
            os.environ["TASKFLOW_DB"] = self._old
        self._tmp.cleanup()

    def test_empty_list_is_success(self):
        self.assertEqual(list_tasks(), [])

    def test_create_starts_as_todo_and_description_optional(self):
        task = create_task(TaskCreate(title="  첫 카드 "))
        self.assertEqual(task.title, "첫 카드")
        self.assertEqual(task.description, "")
        self.assertEqual(task.status, "TODO")

    def test_list_in_id_order(self):
        create_task(TaskCreate(title="a", description="x"))
        create_task(TaskCreate(title="b"))
        self.assertEqual([t.title for t in list_tasks()], ["a", "b"])

    def test_blank_title_rejected_and_not_saved(self):
        for bad in [None, "", "   "]:
            with self.subTest(bad=bad):
                with self.assertRaises(HTTPException) as cm:
                    create_task(TaskCreate(title=bad))
                self.assertEqual(cm.exception.status_code, 422)
        self.assertEqual(list_tasks(), [])


class TaskChangeTest(TasksApiTest):
    def _code(self, fn, *args):
        with self.assertRaises(HTTPException) as cm:
            fn(*args)
        return cm.exception.status_code

    def test_every_status_transition(self):
        states = ["TODO", "IN_PROGRESS", "DONE"]
        for src in states:
            for dst in states:
                with self.subTest(src=src, dst=dst):
                    t = create_task(TaskCreate(title="x"))
                    change_status(t.id, StatusChange(status=src))
                    self.assertEqual(change_status(t.id, StatusChange(status=dst)).status, dst)
                    self.assertEqual(
                        [x.status for x in list_tasks() if x.id == t.id], [dst]
                    )

    def test_invalid_status_rejected_and_unchanged(self):
        t = create_task(TaskCreate(title="x"))
        for bad in [None, "", "done", "DOING"]:
            with self.subTest(bad=bad):
                self.assertEqual(self._code(change_status, t.id, StatusChange(status=bad)), 422)
        self.assertEqual(list_tasks()[0].status, "TODO")

    def test_update_title_and_description_keeps_status(self):
        t = create_task(TaskCreate(title="a", description="d"))
        change_status(t.id, StatusChange(status="DONE"))
        u = update_task(t.id, TaskUpdate(title=" b ", description="e"))
        self.assertEqual((u.title, u.description, u.status), ("b", "e", "DONE"))

    def test_update_only_sent_fields(self):
        t = create_task(TaskCreate(title="a", description="d"))
        self.assertEqual(update_task(t.id, TaskUpdate(description="e")).title, "a")
        self.assertEqual(update_task(t.id, TaskUpdate(title="b")).description, "e")

    def test_update_blank_title_rejected_and_unchanged(self):
        t = create_task(TaskCreate(title="a", description="d"))
        for bad in [None, "", "  "]:
            with self.subTest(bad=bad):
                self.assertEqual(self._code(update_task, t.id, TaskUpdate(title=bad)), 422)
        self.assertEqual((list_tasks()[0].title, list_tasks()[0].description), ("a", "d"))

    def test_missing_card_rejected(self):
        self.assertEqual(self._code(update_task, 999, TaskUpdate(title="x")), 404)
        self.assertEqual(self._code(change_status, 999, StatusChange(status="DONE")), 404)
        self.assertEqual(self._code(delete_task, 999), 404)

    def test_delete_removes_card(self):
        a = create_task(TaskCreate(title="a"))
        b = create_task(TaskCreate(title="b"))
        delete_task(a.id)
        self.assertEqual([t.id for t in list_tasks()], [b.id])
        self.assertEqual(self._code(delete_task, a.id), 404)


if __name__ == "__main__":
    unittest.main()
