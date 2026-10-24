"""Fast endpoint checks that never call Gemini or write complaint records."""

import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

import main
from civic_agent.security import MAX_IMAGE_BYTES, _events

JPEG = b"\xff\xd8\xffdemo\xff\xd9"


class ApiSafetyTests(unittest.TestCase):
    def setUp(self):
        _events.clear()
        self.client = TestClient(main.app)

    def file(self, data=JPEG, **fields):
        return self.client.post(
            "/api/complaints",
            data={"area_name": "Navrangpura", **fields},
            files={"photo": ("capture.jpg", data, "image/jpeg")},
        )

    def test_rejects_invalid_and_oversized_images(self):
        self.assertEqual(self.file(b"not a photo").status_code, 415)
        self.assertEqual(self.file(b"x" * (MAX_IMAGE_BYTES + 1)).status_code, 413)

    def test_rejects_missing_location_and_long_chat(self):
        self.assertEqual(self.file(area_name="").status_code, 400)
        self.assertEqual(self.client.post("/api/chat", json={"message": "x" * 1001}).status_code, 413)

    def test_filing_spam_is_limited_before_model_call(self):
        response = {"reply": "ok", "trace": [], "tracking_id": None,
                    "meta": {}, "error": None}
        with patch.object(main, "_run", new=AsyncMock(return_value=response)) as run:
            codes = [self.file().status_code for _ in range(13)]
        self.assertEqual(codes, [200] * 12 + [429])
        self.assertEqual(run.await_count, 12)

    def test_chat_spam_is_limited_before_model_call(self):
        response = {"reply": "ok", "trace": [], "tracking_id": None,
                    "meta": {}, "error": None}
        with patch.object(main, "_run", new=AsyncMock(return_value=response)) as run:
            codes = [self.client.post("/api/chat", json={"message": "status"}).status_code
                     for _ in range(41)]
        self.assertEqual(codes, [200] * 40 + [429])
        self.assertEqual(run.await_count, 40)

    def test_public_ticket_list_omits_descriptions_and_sets_headers(self):
        response = self.client.get("/api/complaints")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(response.headers["cache-control"], "no-store")
        if response.json():
            self.assertNotIn("description", response.json()[0])


if __name__ == "__main__":
    unittest.main()
