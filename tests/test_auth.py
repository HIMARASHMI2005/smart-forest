import unittest
import time
import json
from backend.app import create_app
from backend.app.extensions import db
from backend.app.models import User

class TestAuthEndpoints(unittest.TestCase):
    """Integration tests for Authentication API endpoints (Register, Login, /me)."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()
        cls.app_context = cls.app.app_context()
        cls.app_context.push()

    @classmethod
    def tearDownClass(cls):
        cls.app_context.pop()

    def setUp(self):
        # Generate unique test email using timestamp
        ts = int(time.time() * 1000)
        self.test_email = f"test_ranger_{ts}@forest.gov"
        self.test_password = "SecurePassword2026!"
        self.test_name = f"Test Ranger {ts}"
        self.test_phone = "+919876543210"

    def test_registration_and_login_workflow(self):
        """Test complete registration, duplicate prevention, and login flow."""
        # 1. Register new user
        reg_payload = {
            "name": self.test_name,
            "email": self.test_email,
            "phone": self.test_phone,
            "password": self.test_password,
            "emergency_contact": "+919123456789"
        }
        res = self.client.post("/api/auth/register", json=reg_payload)
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["data"]["user"]["email"], self.test_email)

        # 2. Duplicate registration attempt should return 409 Conflict
        res_dup = self.client.post("/api/auth/register", json=reg_payload)
        self.assertEqual(res_dup.status_code, 409)

        # 3. Login with incorrect password should return 401 Unauthorized
        res_fail = self.client.post("/api/auth/login", json={
            "email": self.test_email,
            "password": "WrongPassword123"
        })
        self.assertEqual(res_fail.status_code, 401)

        # 4. Login with correct credentials should return 200 and access_token
        res_login = self.client.post("/api/auth/login", json={
            "email": self.test_email,
            "password": self.test_password
        })
        self.assertEqual(res_login.status_code, 200)
        login_data = res_login.get_json()
        self.assertTrue(login_data["success"])
        token = login_data["data"]["access_token"]
        self.assertIsNotNone(token)

        # 5. Access protected /me endpoint with Bearer token
        headers = {"Authorization": f"Bearer {token}"}
        res_me = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(res_me.status_code, 200)
        me_data = res_me.get_json()
        self.assertEqual(me_data["data"]["user"]["email"], self.test_email)

    def test_short_password_rejection(self):
        """Registration with password < 6 characters must be rejected with 400."""
        payload = {
            "name": "Short Pass User",
            "email": f"short_{int(time.time()*1000)}@forest.gov",
            "phone": "+919876543210",
            "password": "123"
        }
        res = self.client.post("/api/auth/register", json=payload)
        self.assertEqual(res.status_code, 400)

if __name__ == "__main__":
    unittest.main()
