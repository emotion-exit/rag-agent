import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.notes import router as notes_router


test_app = FastAPI()
test_app.include_router(notes_router)


def _authorized_headers() -> dict[str, str]:
    return {"Authorization": "Bearer valid-token"}


class NotesRoutesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(test_app)
        self.current_user = {"id": "user-1", "primary_auth_method": "password"}

        self.resolve_user_patch = patch(
            "app.auth.security._resolve_user_from_token",
            return_value=self.current_user,
        )
        self.resolve_user_patch.start()

    def tearDown(self) -> None:
        self.resolve_user_patch.stop()

    def test_list_notes_route_exists(self) -> None:
        with patch("app.routers.notes.list_notes", return_value=[]):
            response = self.client.get("/api/notes", headers=_authorized_headers())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"items": []})

    def test_submit_note_save_job_route_exists(self) -> None:
        created = {
            "job": {
                "job_id": "job-1",
                "note_id": "note-1",
                "status": "pending",
                "error_message": "",
                "created_at": "now",
                "updated_at": "now",
                "completed_at": "",
            },
            "note": {
                "note_id": "note-1",
                "session_id": "session-1",
                "message_id": "message-1",
                "knowledge_space": "空间A",
                "query": "问题",
                "answer_excerpt": "回答摘要",
                "title": "",
                "status": "pending",
                "current_revision_id": "",
                "last_error": "",
                "created_at": "now",
                "updated_at": "now",
            },
            "payload": {
                "query": "问题",
                "answer": "回答",
                "knowledge_space": "空间A",
                "sources": [],
            },
        }

        with patch("app.routers.notes.create_note_save_job", return_value=created), patch(
            "app.routers.notes.launch_note_save_job"
        ) as launch_mock:
            response = self.client.post(
                "/api/notes/save-jobs",
                headers=_authorized_headers(),
                json={
                    "session_id": "session-1",
                    "message_id": "message-1",
                    "query": "问题",
                    "answer": "回答",
                    "knowledge_space": "空间A",
                    "sources": [],
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        launch_mock.assert_called_once()

    def test_submit_note_revision_requires_existing_note(self) -> None:
        with patch("app.routers.notes.create_note_revision_save_job", return_value=None):
            response = self.client.post(
                "/api/notes/note-404/revision-save-jobs",
                headers=_authorized_headers(),
                json={"answer": "新的回答", "sources": []},
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "笔记不存在")


if __name__ == "__main__":
    unittest.main()