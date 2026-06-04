import importlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


class NailMindAPITestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp(prefix="nailmind-api-test-")
        os.environ["DATA_DIR"] = cls.temp_dir
        os.environ["DATABASE_URL"] = f"sqlite:///{cls.temp_dir}/test.db"
        os.environ["PUBLIC_BASE_URL"] = "http://testserver"
        os.environ["JWT_SECRET"] = "test-secret"
        os.environ["WORKER_TOKEN"] = "test-worker-token"
        os.environ["DEMO_EMAIL"] = "luna@nailmind.app"
        os.environ["DEMO_PASSWORD"] = "123456"

        for module_name in [
            "app.config",
            "app.database",
            "app.models",
            "app.security",
            "app.domain",
            "app.main",
        ]:
            if module_name in sys.modules:
                del sys.modules[module_name]

        cls.app_main = importlib.import_module("app.main")
        from fastapi.testclient import TestClient

        cls.client_cm = TestClient(cls.app_main.app)
        cls.client = cls.client_cm.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client_cm.__exit__(None, None, None)
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def make_image_bytes(self):
        image = Image.new("RGB", (256, 256), (246, 220, 210))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    def auth_header(self, token: str):
        return {"Authorization": f"Bearer {token}"}

    def admin_login(self, email: str, password: str = "123456") -> str:
        response = self.client.post("/admin/auth/login", json={"email": email, "password": password})
        self.assertEqual(response.status_code, 200)
        return response.json()["token"]

    user_counter = 0

    def register_user(self) -> str:
        NailMindAPITestCase.user_counter += 1
        email = f"test{NailMindAPITestCase.user_counter}@example.com"
        register_response = self.client.post(
            "/api/auth/register",
            json={"name": "Test User", "email": email, "password": "123456"},
        )
        self.assertEqual(register_response.status_code, 200)
        return register_response.json()["token"]

    def test_full_auth_upload_tryon_and_worker_flow(self):
        token = self.register_user()

        upload_response = self.client.post(
            "/api/try-on/uploads",
            headers=self.auth_header(token),
            files={"file": ("hand.png", self.make_image_bytes(), "image/png")},
        )
        self.assertEqual(upload_response.status_code, 200)
        object_key = upload_response.json()["objectKey"]
        self.assertTrue(object_key.endswith(".png"))

        job_response = self.client.post(
            "/api/try-on/jobs",
            headers=self.auth_header(token),
            json={
                "styleId": "rose-mist",
                "sourceImageKey": object_key,
                "selectedLength": "natural_short",
                "selectedShape": "squoval",
            },
        )
        self.assertEqual(job_response.status_code, 200)
        job_code = job_response.json()["id"]

        claim_response = self.client.post(
            "/internal/try-on/jobs/claim",
            headers={"X-Worker-Token": "test-worker-token"},
        )
        self.assertEqual(claim_response.status_code, 200)
        job_payload = claim_response.json()["job"]
        self.assertEqual(job_payload["id"], job_code)

        result_path = Path(job_payload["resultImagePath"])
        result_path.parent.mkdir(parents=True, exist_ok=True)
        with result_path.open("wb") as f:
            f.write(self.make_image_bytes())

        progress_response = self.client.post(
            f"/internal/try-on/jobs/{job_code}/progress",
            headers={"X-Worker-Token": "test-worker-token"},
            json={"stage": "rendering", "progress": 75},
        )
        self.assertEqual(progress_response.status_code, 200)

        complete_response = self.client.post(
            f"/internal/try-on/jobs/{job_code}/complete",
            headers={"X-Worker-Token": "test-worker-token"},
            json={
                "resultImageKey": job_payload["resultImageKey"],
                "detectedTraits": {"backend": "test", "shape": "squoval"},
            },
        )
        self.assertEqual(complete_response.status_code, 200)

        result_response = self.client.get(
            f"/api/try-on/jobs/{job_code}/result",
            headers=self.auth_header(token),
        )
        self.assertEqual(result_response.status_code, 200)
        result_json = result_response.json()
        self.assertEqual(result_json["status"], "completed")
        self.assertIn("resultImageUrl", result_json)

        image_response = self.client.get(
            f"/api/try-on/jobs/{job_code}/result-image",
            headers=self.auth_header(token),
        )
        self.assertEqual(image_response.status_code, 200)
        self.assertEqual(image_response.headers["content-type"], "image/png")

    def test_client_facing_api_surface(self):
        token = self.register_user()
        headers = self.auth_header(token)

        auth_me_response = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(auth_me_response.status_code, 200)
        self.assertTrue(auth_me_response.json()["user"]["email"].startswith("test"))

        home_response = self.client.get("/api/home", headers=headers)
        self.assertEqual(home_response.status_code, 200)
        self.assertGreaterEqual(len(home_response.json()["recommended"]), 1)

        styles_response = self.client.get("/api/styles", headers=headers)
        self.assertEqual(styles_response.status_code, 200)
        styles_items = styles_response.json()["items"]
        self.assertGreaterEqual(len(styles_items), 2)
        style_id = styles_items[0]["id"]

        filtered_styles_response = self.client.get("/api/styles", params={"tag": "法式"}, headers=headers)
        self.assertEqual(filtered_styles_response.status_code, 200)
        self.assertGreaterEqual(len(filtered_styles_response.json()["items"]), 1)

        search_response = self.client.get("/api/styles/search", params={"q": "猫眼"}, headers=headers)
        self.assertEqual(search_response.status_code, 200)
        self.assertEqual(search_response.json()["query"], "猫眼")

        style_detail_response = self.client.get(f"/api/styles/{style_id}", headers=headers)
        self.assertEqual(style_detail_response.status_code, 200)
        self.assertEqual(style_detail_response.json()["style"]["id"], style_id)

        favorites_initial = self.client.get("/api/favorites", headers=headers)
        self.assertEqual(favorites_initial.status_code, 200)
        self.assertEqual(favorites_initial.json()["items"], [])

        add_favorite_response = self.client.post(f"/api/favorites/{style_id}", headers=headers)
        self.assertEqual(add_favorite_response.status_code, 200)
        self.assertTrue(add_favorite_response.json()["favorited"])

        favorites_after_add = self.client.get("/api/favorites", headers=headers)
        self.assertEqual(favorites_after_add.status_code, 200)
        self.assertEqual(len(favorites_after_add.json()["items"]), 1)

        remove_favorite_response = self.client.delete(f"/api/favorites/{style_id}", headers=headers)
        self.assertEqual(remove_favorite_response.status_code, 200)
        self.assertFalse(remove_favorite_response.json()["favorited"])

        stores_response = self.client.get("/api/stores", headers=headers)
        self.assertEqual(stores_response.status_code, 200)
        stores_items = stores_response.json()["items"]
        self.assertGreaterEqual(len(stores_items), 1)
        store_id = stores_items[0]["id"]
        slot = stores_items[0]["slots"][0]

        store_detail_response = self.client.get(f"/api/stores/{store_id}", headers=headers)
        self.assertEqual(store_detail_response.status_code, 200)
        self.assertEqual(store_detail_response.json()["id"], store_id)

        store_slots_response = self.client.get(f"/api/stores/{store_id}/slots", headers=headers)
        self.assertEqual(store_slots_response.status_code, 200)
        self.assertIn(slot, store_slots_response.json()["slots"])

        create_booking_response = self.client.post(
            "/api/bookings",
            headers=headers,
            json={
                "storeId": store_id,
                "styleId": style_id,
                "slot": slot,
                "name": "Test User",
                "phone": "13800138000",
                "note": "靠窗位",
            },
        )
        self.assertEqual(create_booking_response.status_code, 200)
        booking = create_booking_response.json()
        booking_id = booking["id"]

        bookings_response = self.client.get("/api/bookings", headers=headers)
        self.assertEqual(bookings_response.status_code, 200)
        self.assertEqual(len(bookings_response.json()["items"]), 1)

        booking_detail_response = self.client.get(f"/api/bookings/{booking_id}", headers=headers)
        self.assertEqual(booking_detail_response.status_code, 200)
        self.assertEqual(booking_detail_response.json()["id"], booking_id)

        confirm_booking_response = self.client.post(f"/api/bookings/{booking_id}/confirm", headers=headers)
        self.assertEqual(confirm_booking_response.status_code, 200)
        self.assertEqual(confirm_booking_response.json()["status"], "confirmed")

        profile_response = self.client.get("/api/profile", headers=headers)
        self.assertEqual(profile_response.status_code, 200)
        profile_json = profile_response.json()
        self.assertEqual(profile_json["favoritesCount"], 0)
        self.assertEqual(profile_json["bookingCount"], 1)

        settings_response = self.client.get("/api/settings", headers=headers)
        self.assertEqual(settings_response.status_code, 200)
        self.assertIn("stylePreferences", settings_response.json())

        logout_response = self.client.post("/api/auth/logout", headers=headers)
        self.assertEqual(logout_response.status_code, 200)
        self.assertEqual(logout_response.json()["status"], "logged_out")

        auth_after_logout = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(auth_after_logout.status_code, 401)

    def test_admin_and_merchant_operating_flow(self):
        user_token = self.register_user()
        user_headers = self.auth_header(user_token)

        styles_response = self.client.get("/api/styles", headers=user_headers)
        self.assertEqual(styles_response.status_code, 200)
        style_id = styles_response.json()["items"][0]["id"]

        self.client.get(f"/api/styles/{style_id}", headers=user_headers)
        self.client.post(f"/api/favorites/{style_id}", headers=user_headers)

        stores_response = self.client.get("/api/stores", headers=user_headers)
        store_id = stores_response.json()["items"][0]["id"]
        slot = stores_response.json()["items"][0]["slots"][0]
        self.client.post(
            "/api/bookings",
            headers=user_headers,
            json={
                "storeId": store_id,
                "styleId": style_id,
                "slot": slot,
                "name": "运营测试",
                "phone": "13800138000",
                "note": "",
            },
        )

        merchant_token = self.admin_login("merchant@nailmind.app")
        merchant_headers = self.auth_header(merchant_token)

        merchant_me = self.client.get("/admin/auth/me", headers=merchant_headers)
        self.assertEqual(merchant_me.status_code, 200)
        self.assertEqual(merchant_me.json()["user"]["role"], "merchant_admin")

        merchant_dashboard = self.client.get("/admin/merchants/me/dashboard", headers=merchant_headers)
        self.assertEqual(merchant_dashboard.status_code, 200)

        request_response = self.client.post(
            "/admin/merchants/me/requests",
            headers=merchant_headers,
            json={"styleId": style_id, "requestedAction": "launch", "reason": "申请继续在门店可售"},
        )
        self.assertEqual(request_response.status_code, 200)
        request_id = request_response.json()["request"]["id"]

        admin_token = self.admin_login("operator@nailmind.app")
        admin_headers = self.auth_header(admin_token)

        overview_response = self.client.get("/admin/analytics/overview", headers=admin_headers)
        self.assertEqual(overview_response.status_code, 200)
        self.assertGreaterEqual(overview_response.json()["funnel"]["impressions"], 1)

        requests_response = self.client.get("/admin/requests", headers=admin_headers)
        self.assertEqual(requests_response.status_code, 200)
        self.assertTrue(any(item["id"] == request_id for item in requests_response.json()["items"]))

        approve_request_response = self.client.post(
            f"/admin/requests/{request_id}/approve",
            headers=admin_headers,
            json={"reviewNote": "继续保留在售"},
        )
        self.assertEqual(approve_request_response.status_code, 200)
        self.assertEqual(approve_request_response.json()["request"]["status"], "approved")

        recommendations_response = self.client.get("/admin/trends/recommendations", headers=admin_headers)
        self.assertEqual(recommendations_response.status_code, 200)
        recommendation_id = recommendations_response.json()["items"][0]["id"]

        approve_recommendation_response = self.client.post(
            f"/admin/trends/recommendations/{recommendation_id}/approve",
            headers=admin_headers,
            json={"reviewNote": "允许执行"},
        )
        self.assertEqual(approve_recommendation_response.status_code, 200)
        self.assertEqual(approve_recommendation_response.json()["recommendation"]["status"], "approved")

        style_analytics_response = self.client.get(f"/admin/analytics/styles/{style_id}", headers=admin_headers)
        self.assertEqual(style_analytics_response.status_code, 200)
        self.assertEqual(style_analytics_response.json()["style"]["id"], style_id)


if __name__ == "__main__":
    unittest.main()
