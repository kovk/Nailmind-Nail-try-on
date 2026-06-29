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

ROOT_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


class NailMindAPITestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.chdir(PROJECT_ROOT)
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
        cls.seed_admin_users()

    @classmethod
    def seed_admin_users(cls):
        from app.database import SessionLocal
        from app.models import Merchant, Store, User
        from app.security import hash_password

        with SessionLocal() as db:
            merchant = db.query(Merchant).filter(Merchant.code == "test-merchant").first()
            if not merchant:
                merchant = Merchant(code="test-merchant", name="测试商家")
                db.add(merchant)
                db.flush()
            store = db.query(Store).filter(Store.code == "test-store").first()
            if not store:
                store = Store(
                    code="test-store",
                    merchant_id=merchant.id,
                    name="测试门店",
                    distance="1.0km",
                    price_band="¥199 起",
                    score="4.9",
                    slots_json='["明天 10:00"]',
                    open_hours="10:00-20:00",
                    artists=2,
                    works="20",
                    is_accepting_bookings=True,
                )
                db.add(store)

            users = [
                ("operator@nailmind.app", "运营管理员", "platform_admin", None),
                ("merchant@nailmind.app", "商家管理员", "merchant_admin", merchant.id),
            ]
            for email, name, role, merchant_id in users:
                user = db.query(User).filter(User.email == email).first()
                if not user:
                    db.add(
                        User(
                            email=email,
                            password_hash=hash_password("123456"),
                            name=name,
                            role=role,
                            merchant_id=merchant_id,
                            managed_store_code="test-store" if role == "merchant_admin" else None,
                        )
                    )
                elif role == "merchant_admin":
                    user.managed_store_code = "test-store"
                    user.merchant_id = merchant.id
            db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.client_cm.__exit__(None, None, None)
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def make_image_bytes(self):
        image = Image.new("RGB", (512, 512), (246, 220, 210))
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

    def test_full_auth_upload_tryon_job_flow(self):
        token = self.register_user()
        headers = self.auth_header(token)

        style_list_response = self.client.get("/api/styles", headers=headers)
        self.assertEqual(style_list_response.status_code, 200)
        first_style = style_list_response.json()["items"][0]
        style_id = first_style["id"]

        from app.database import SessionLocal
        from app.models import NailStyleAsset

        style_image_path = Path(self.temp_dir) / "style-async.png"
        style_image_path.write_bytes(self.make_image_bytes())
        with SessionLocal() as db:
            asset = db.get(NailStyleAsset, first_style["tryOnStyleId"])
            asset.local_image_path = str(style_image_path)
            db.add(asset)
            db.commit()

        def fake_generate_tryon_image(source_path: str, style_path: str, result_path: str):
            Path(result_path).parent.mkdir(parents=True, exist_ok=True)
            Path(result_path).write_bytes(self.make_image_bytes())
            return True, "test image generated"

        original_generate_tryon_image = self.app_main.generate_tryon_image
        self.app_main.generate_tryon_image = fake_generate_tryon_image

        try:
            upload_response = self.client.post(
                "/api/try-on/uploads",
                headers=headers,
                files={"file": ("hand.png", self.make_image_bytes(), "image/png")},
            )
            self.assertEqual(upload_response.status_code, 200)
            object_key = upload_response.json()["objectKey"]
            self.assertTrue(object_key.endswith(".jpg"))

            job_response = self.client.post(
                "/api/try-on/jobs",
                headers=headers,
                json={
                    "styleId": style_id,
                    "sourceImageKey": object_key,
                    "selectedLength": "natural_short",
                    "selectedShape": "squoval",
                },
            )
            self.assertEqual(job_response.status_code, 200)
            job_code = job_response.json()["id"]
        finally:
            self.app_main.generate_tryon_image = original_generate_tryon_image

        result_response = self.client.get(
            f"/api/try-on/jobs/{job_code}/result",
            headers=headers,
        )
        self.assertEqual(result_response.status_code, 200)
        result_json = result_response.json()
        self.assertEqual(result_json["status"], "completed")
        self.assertIn("resultImageUrl", result_json)

        image_response = self.client.get(
            f"/api/try-on/jobs/{job_code}/result-image",
            headers=headers,
        )
        self.assertEqual(image_response.status_code, 200)
        self.assertEqual(image_response.headers["content-type"], "image/png")

    def test_sync_tryon_flow_and_history(self):
        token = self.register_user()
        headers = self.auth_header(token)

        upload_response = self.client.post(
            "/api/tryon/upload-hand",
            headers=headers,
            files={"file": ("hand-sync.png", self.make_image_bytes(), "image/png")},
        )
        self.assertEqual(upload_response.status_code, 200)
        hand_payload = upload_response.json()
        self.assertIn("hand_id", hand_payload)

        style_list_response = self.client.get("/api/styles", headers=headers)
        self.assertEqual(style_list_response.status_code, 200)
        first_style = style_list_response.json()["items"][0]
        self.assertIn("tryOnStyleId", first_style)
        self.assertIsNotNone(first_style["tryOnStyleId"])

        from app.database import SessionLocal
        from app.models import NailStyleAsset

        style_image_path = Path(self.temp_dir) / "style-sync.png"
        style_image_path.write_bytes(self.make_image_bytes())
        with SessionLocal() as db:
            asset = db.get(NailStyleAsset, first_style["tryOnStyleId"])
            asset.local_image_path = str(style_image_path)
            db.add(asset)
            db.commit()

        cached_result_path = Path(self.temp_dir) / "results" / f"{hand_payload['hand_id']}+style_01+natural_short+squoval.png"
        cached_result_path.parent.mkdir(parents=True, exist_ok=True)
        cached_result_path.write_bytes(self.make_image_bytes())

        sync_response = self.client.post(
            "/api/tryon/try-on",
            headers=headers,
            json={
                "handId": hand_payload["hand_id"],
                "styleId": first_style["tryOnStyleId"],
                "selectedLength": "natural_short",
                "selectedShape": "squoval",
            },
        )
        self.assertEqual(sync_response.status_code, 200)
        sync_json = sync_response.json()
        self.assertEqual(sync_json["source"], "bailian-cached")
        self.assertIn("/files/results/", sync_json["result_url"])

        result_image_response = self.client.get(sync_json["result_url"], headers=headers)
        self.assertEqual(result_image_response.status_code, 200)
        self.assertEqual(result_image_response.headers["content-type"], "image/png")

        history_response = self.client.get("/api/tryon/history", headers=headers)
        self.assertEqual(history_response.status_code, 200)
        history_json = history_response.json()
        self.assertGreaterEqual(history_json["total"], 1)
        self.assertEqual(history_json["items"][0]["styleId"], first_style["id"])

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
        self.assertIn("imageUrl", styles_items[0])
        self.assertIn("tryOnStyleId", styles_items[0])
        style_id = styles_items[0]["id"]

        filter_tag = styles_items[0]["tags"][0] if styles_items[0].get("tags") else styles_items[0]["name"]
        filtered_styles_response = self.client.get("/api/styles", params={"tag": filter_tag}, headers=headers)
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
        expected_booking_count = 0
        if stores_items:
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
            expected_booking_count = 1

            booking_detail_response = self.client.get(f"/api/bookings/{booking_id}", headers=headers)
            self.assertEqual(booking_detail_response.status_code, 200)
            self.assertEqual(booking_detail_response.json()["id"], booking_id)

            confirm_booking_response = self.client.post(f"/api/bookings/{booking_id}/confirm", headers=headers)
            self.assertEqual(confirm_booking_response.status_code, 200)
            self.assertEqual(confirm_booking_response.json()["status"], "confirmed")

        bookings_response = self.client.get("/api/bookings", headers=headers)
        self.assertEqual(bookings_response.status_code, 200)
        self.assertEqual(len(bookings_response.json()["items"]), expected_booking_count)

        profile_response = self.client.get("/api/profile", headers=headers)
        self.assertEqual(profile_response.status_code, 200)
        profile_json = profile_response.json()
        self.assertEqual(profile_json["favoritesCount"], 0)
        self.assertEqual(profile_json["bookingCount"], expected_booking_count)

        settings_response = self.client.get("/api/settings", headers=headers)
        self.assertEqual(settings_response.status_code, 200)
        self.assertIn("stylePreferences", settings_response.json())

        logout_response = self.client.post("/api/auth/logout", headers=headers)
        self.assertEqual(logout_response.status_code, 200)
        self.assertEqual(logout_response.json()["status"], "logged_out")

        auth_after_logout = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(auth_after_logout.status_code, 401)

    def test_tryon_quality_metrics_use_real_records_and_eval_events(self):
        from app.database import SessionLocal
        from app.models import EventLog, NailStyleAsset, TryOnRecord

        with SessionLocal() as db:
            db.query(TryOnRecord).delete(synchronize_session=False)
            db.query(EventLog).filter(
                EventLog.event_name.in_(("tryon_quality_eval", "tryon_manual_eval", "tryon_model_eval"))
            ).delete(synchronize_session=False)
            asset = db.query(NailStyleAsset).filter(NailStyleAsset.style_code == "style-01").first()
            self.assertIsNotNone(asset)
            db.add_all(
                [
                    TryOnRecord(
                        user_id=None,
                        hand_image_id=None,
                        nail_style_asset_id=asset.id,
                        result_url="http://testserver/files/results/quality-a.png",
                        source="bailian-live",
                        duration_ms=8000,
                    ),
                    TryOnRecord(
                        user_id=None,
                        hand_image_id=None,
                        nail_style_asset_id=asset.id,
                        result_url="http://testserver/files/results/quality-b.png",
                        source="bailian-live",
                        duration_ms=12000,
                    ),
                    EventLog(
                        event_id="tryon-quality-metric-a",
                        event_name="tryon_quality_eval",
                        style_id="style-01",
                        payload_json=json.dumps({"styleFidelity": 0.91, "manualConsistency": 0.86}),
                    ),
                    EventLog(
                        event_id="tryon-quality-metric-b",
                        event_name="tryon_model_eval",
                        style_id="style-01",
                        payload_json=json.dumps({"styleFidelity": 95, "manualConsistency": 90}),
                    ),
                ]
            )
            db.commit()

            metrics = self.app_main.build_tryon_quality_metrics(db, days=7)

        self.assertEqual(metrics["averageDuration"]["status"], "measured")
        self.assertEqual(metrics["averageDuration"]["averageMs"], 10000.0)
        self.assertEqual(metrics["averageDuration"]["sampleSize"], 2)
        self.assertEqual(metrics["averageDuration"]["confidenceLevel"], 0.99)
        self.assertGreater(metrics["averageDuration"]["ciHalfWidthMs"], 0)
        self.assertEqual(metrics["styleFidelity"]["score"], 0.93)
        self.assertEqual(metrics["manualConsistency"]["score"], 0.88)
        self.assertIn("脱敏聚合指标", metrics["privacyPolicy"]["resultDisplay"])

    def test_admin_and_merchant_operating_flow(self):
        user_token = self.register_user()
        user_headers = self.auth_header(user_token)

        styles_response = self.client.get("/api/styles", headers=user_headers)
        self.assertEqual(styles_response.status_code, 200)
        style_id = styles_response.json()["items"][0]["id"]

        self.client.get(f"/api/styles/{style_id}", headers=user_headers)
        self.client.post(f"/api/favorites/{style_id}", headers=user_headers)

        stores_response = self.client.get("/api/stores", headers=user_headers)
        self.assertEqual(stores_response.status_code, 200)
        stores = stores_response.json()["items"]
        if stores:
            store_id = stores[0]["id"]
            slot = stores[0]["slots"][0]
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
        recommendation_items = recommendations_response.json()["items"]
        if recommendation_items:
            recommendation_id = recommendation_items[0]["id"]
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
