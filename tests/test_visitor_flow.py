import unittest
import base64
import numpy as np
import cv2
import json
from backend.app import create_app
from backend.app.services.visitor_service import db_conn


class TestVisitorFlow(unittest.TestCase):
    """Integration test suite for visitor registration, biometric passes, and officer dashboard APIs."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()

    def test_pages_render(self):
        """Verify frontend templates render with HTTP 200."""
        res_reg = self.client.get("/register")
        self.assertEqual(res_reg.status_code, 200)
        # Badge text is uppercase in consolidated template
        self.assertIn(b"FOREST VISITOR REGISTRATION", res_reg.data)
        self.assertIn(b"SMART FOREST", res_reg.data)

        res_off = self.client.get("/officer")
        self.assertEqual(res_off.status_code, 200)
        # Title includes 'Officer Command Dashboard'
        self.assertIn(b"Officer Command", res_off.data)

        # Root "/" now serves the landing page (index.html)
        res_root = self.client.get("/")
        self.assertEqual(res_root.status_code, 200)
        # Landing page has 'Smart Forest' in multiple places
        self.assertIn(b"Smart Forest", res_root.data)

    def test_visitor_registration_and_pass(self):
        """Test visitor registration without face (legacy /api/register endpoint)."""
        payload = {
            "name": "Arjun Das",
            "phone": "+91 9876543210",
            "email": "arjun@trekker.org"
        }
        res = self.client.post("/api/register", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("success"), f"Registration failed: {data}")
        uid = data.get("unique_id")
        self.assertIsNotNone(uid, f"unique_id missing in response: {data}")
        self.assertTrue(uid.startswith("FOR-"), f"unexpected uid format: {uid}")
        self.assertEqual(data["name"], "Arjun Das")
        self.assertFalse(data["face_registered"])

    def test_visitor_registration_with_face_biometrics(self):
        """Test visitor registration validates real photographs and rejects synthetic placeholders."""
        from backend.app.services.visitor_service import delete_registered_visitor

        # 1. Synthetic smiley face MUST be rejected with HTTP 400
        test_face = np.ones((100, 100, 3), dtype=np.uint8) * 180
        cv2.circle(test_face, (35, 40), 8, (30, 30, 30), -1)
        cv2.circle(test_face, (65, 40), 8, (30, 30, 30), -1)
        cv2.ellipse(test_face, (50, 70), (20, 8), 0, 0, 180, (20, 20, 120), 2)
        _, enc_fake = cv2.imencode(".jpg", test_face)
        b64_fake = "data:image/jpeg;base64," + base64.b64encode(enc_fake).decode("utf-8")

        fake_payload = {
            "name": "Synthetic Test",
            "phone": "+91 9123456781",
            "email": "synthetic@test.org",
            "face_image": b64_fake
        }
        res_fake = self.client.post("/api/register", json=fake_payload)
        self.assertEqual(res_fake.status_code, 400)
        self.assertIn("Photo capture failed", res_fake.get_json().get("error", ""))

        # 2. Genuine real photograph MUST be accepted with HTTP 200
        real_img = cv2.imread("dataset/faces/ranger_priya/face_01.jpg")
        self.assertIsNotNone(real_img, "Failed to load real photographic test fixture")
        _, enc_real = cv2.imencode(".jpg", real_img)
        b64_real = "data:image/jpeg;base64," + base64.b64encode(enc_real).decode("utf-8")

        payload = {
            "name": "Kavita Nair",
            "phone": "+91 9123456780",
            "email": "kavita.nair@eco.org",
            "face_image": b64_real
        }
        res = self.client.post("/api/register", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertTrue(data["unique_id"].startswith("FOR-"))
        self.assertTrue(data["face_registered"])
        self.assertTrue(len(data["face_thumbnail"]) > 0)

        uid = data["unique_id"]

        # Test GPS update
        gps_res = self.client.post("/api/gps-update", json={
            "unique_id": uid,
            "latitude": 11.6543,
            "longitude": 76.6234,
            "gps_status": "Tracking Live"
        })
        self.assertEqual(gps_res.status_code, 200)

        # Verify in registrations list
        reg_list = self.client.get("/api/registrations").get_json()
        found = [v for v in reg_list if v["unique_id"] == uid]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["name"], "Kavita Nair")
        self.assertAlmostEqual(found[0]["latitude"], 11.6543, places=3)

        # Clean up test user to keep dataset/faces pristine
        delete_registered_visitor(uid)

    def test_emergency_sos_flow(self):
        """Test emergency SOS distress broadcast."""
        sos_res = self.client.post("/api/sos", data={
            "unique_id": "FOR-TEST",
            "name": "Emergency Test User",
            "latitude": 11.6600,
            "longitude": 76.6300
        })
        self.assertEqual(sos_res.status_code, 200)
        data = sos_res.get_json()
        self.assertTrue(data["success"])

        # Check in SOS alerts list
        alerts_res = self.client.get("/api/sos-alerts").get_json()
        self.assertTrue(any(a["name"] == "Emergency Test User" for a in alerts_res))

    def test_perimeter_detection_endpoint(self):
        """Test POST /api/detect with sample image."""
        test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        _, enc = cv2.imencode(".jpg", test_frame)
        res = self.client.post("/api/detect", json={
            "image": "data:image/jpeg;base64," + base64.b64encode(enc).decode("utf-8")
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("people", data)
        self.assertIn("zone", data)
        self.assertIn("total_detected", data)

    def test_dataset_stats_and_export(self):
        """Test dataset-stats reporting 100% real images and CSV export."""
        stats = self.client.get("/api/dataset-stats").get_json()
        self.assertTrue(stats["real_images_only"])
        self.assertEqual(stats["synthetic_images_count"], 0)
        export = self.client.get("/api/export-registry")
        self.assertEqual(export.status_code, 200)
        self.assertIn(b"Unique_ID", export.data)
        self.assertIn(b"Visitor_Name", export.data.replace(b"Name", b"Visitor_Name"))

    @classmethod
    def tearDownClass(cls):
        """Clean up test records."""
        with db_conn() as db:
            db.execute("DELETE FROM registrations WHERE email LIKE '%@trekker.org' OR email LIKE '%@eco.org'")
            db.execute("DELETE FROM visitor_face_embeddings WHERE name IN ('Kavita Nair', 'Arjun Das')")
            db.execute("DELETE FROM events WHERE details LIKE '%Emergency Test User%'")


if __name__ == "__main__":
    unittest.main()

