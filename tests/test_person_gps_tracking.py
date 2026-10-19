import unittest
import time
from unittest.mock import patch
from flask_jwt_extended import create_access_token
from shapely.geometry import Point, shape

from backend.app import create_app
from backend.app.extensions import db
from backend.app.models import User, Location, SOSEvent, ForestZone
from backend.app.services.geofence_service import GeofenceService


class TestPersonGPSTracking(unittest.TestCase):
    """
    Comprehensive tests for Real-Time Registered Person GPS Tracking:
    - Real browser GPS ingestion (latitude, longitude, accuracy, altitude, heading, speed)
    - Authentication enforcement via JWT
    - Input validation (bounds checking)
    - Full location history preservation in database
    - Exact coordinate preservation (never replaced by zone centroid)
    - Shapely Point-in-Polygon zone detection: Point(longitude, latitude)
    - Multi-user isolation (User A vs User B)
    - /api/location/current and /api/admin/locations/current
    - Socket.IO location broadcast verification
    - Real GPS in SOS events
    """

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()
        cls.app_context = cls.app.app_context()
        cls.app_context.push()

        # Create test User A (Rahul)
        cls.user_a = User.query.filter_by(email="rahul.test@forest.gov").first()
        if not cls.user_a:
            cls.user_a = User(
                name="Rahul",
                email="rahul.test@forest.gov",
                phone="+919876543201",
                role="USER",
                status="ACTIVE"
            )
            cls.user_a.set_password("SecurePass123!")
            db.session.add(cls.user_a)

        # Create test User B (Priya)
        cls.user_b = User.query.filter_by(email="priya.test@forest.gov").first()
        if not cls.user_b:
            cls.user_b = User(
                name="Priya",
                email="priya.test@forest.gov",
                phone="+919876543202",
                role="USER",
                status="ACTIVE"
            )
            cls.user_b.set_password("SecurePass123!")
            db.session.add(cls.user_b)

        # Create test Admin
        cls.admin_user = User.query.filter_by(email="admin.test@forest.gov").first()
        if not cls.admin_user:
            cls.admin_user = User(
                name="Admin Officer",
                email="admin.test@forest.gov",
                phone="+919876543299",
                role="ADMIN",
                status="ACTIVE"
            )
            cls.admin_user.set_password("AdminPass123!")
            db.session.add(cls.admin_user)

        db.session.commit()

        cls.token_a = create_access_token(identity=str(cls.user_a.id))
        cls.token_b = create_access_token(identity=str(cls.user_b.id))
        cls.token_admin = create_access_token(identity=str(cls.admin_user.id))

    @classmethod
    def tearDownClass(cls):
        try:
            Location.query.filter(Location.user_id.in_([cls.user_a.id, cls.user_b.id, cls.admin_user.id])).delete()
            SOSEvent.query.filter(SOSEvent.user_id.in_([cls.user_a.id, cls.user_b.id, cls.admin_user.id])).delete()
            db.session.commit()
        except Exception:
            db.session.rollback()
        cls.app_context.pop()

    def test_01_location_update_requires_auth(self):
        """POST /api/location/update without JWT token must return 401 Unauthorized."""
        res = self.client.post("/api/location/update", json={
            "latitude": 11.65600,
            "longitude": 76.62750
        })
        self.assertEqual(res.status_code, 401)

    def test_02_valid_gps_stored_with_authenticated_user_id(self):
        """Valid coordinates must be stored in the database with the authenticated user_id."""
        gps_lat = 11.65600
        gps_lon = 76.62750
        accuracy = 6.4

        headers = {"Authorization": f"Bearer {self.token_a}"}
        # Note: Client maliciously attempts to send another user_id=9999
        payload = {
            "latitude": gps_lat,
            "longitude": gps_lon,
            "accuracy": accuracy,
            "user_id": 9999
        }
        res = self.client.post("/api/location/update", headers=headers, json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])

        # Check returned user_id is the authenticated User A, NOT the spoofed 9999
        self.assertEqual(data["data"]["user_id"], self.user_a.id)

        # Check stored location in database
        latest = Location.query.filter_by(user_id=self.user_a.id).order_by(Location.id.desc()).first()
        self.assertIsNotNone(latest)
        self.assertEqual(latest.user_id, self.user_a.id)
        self.assertAlmostEqual(float(latest.latitude), gps_lat, places=5)
        self.assertAlmostEqual(float(latest.longitude), gps_lon, places=5)
        self.assertAlmostEqual(latest.accuracy, accuracy, places=1)

    def test_03_invalid_coordinates_rejected_with_400(self):
        """Out-of-bounds latitude (>90, <-90) and longitude (>180, <-180) must return 400."""
        headers = {"Authorization": f"Bearer {self.token_a}"}

        # Latitude out of bounds
        res = self.client.post("/api/location/update", headers=headers, json={
            "latitude": 95.0,
            "longitude": 76.62750
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("out of bounds", res.get_json()["message"].lower())

        # Longitude out of bounds
        res2 = self.client.post("/api/location/update", headers=headers, json={
            "latitude": 11.65600,
            "longitude": 185.0
        })
        self.assertEqual(res2.status_code, 400)
        self.assertIn("out of bounds", res2.get_json()["message"].lower())

        # Missing latitude
        res3 = self.client.post("/api/location/update", headers=headers, json={
            "longitude": 76.62750
        })
        self.assertEqual(res3.status_code, 400)

        # Non-numeric coordinate
        res4 = self.client.post("/api/location/update", headers=headers, json={
            "latitude": "not_a_number",
            "longitude": 76.62750
        })
        self.assertEqual(res4.status_code, 400)

    def test_04_telemetry_fields_stored(self):
        """Accuracy, altitude, heading, and speed telemetry must be stored properly."""
        headers = {"Authorization": f"Bearer {self.token_a}"}
        payload = {
            "latitude": 11.65610,
            "longitude": 76.62760,
            "accuracy": 4.5,
            "altitude": 850.2,
            "heading": 175.5,
            "speed": 1.4
        }
        res = self.client.post("/api/location/update", headers=headers, json=payload)
        self.assertEqual(res.status_code, 200)

        latest = Location.query.filter_by(user_id=self.user_a.id).order_by(Location.id.desc()).first()
        self.assertIsNotNone(latest)
        self.assertAlmostEqual(latest.accuracy, 4.5, places=1)
        self.assertAlmostEqual(latest.altitude, 850.2, places=1)
        self.assertAlmostEqual(latest.heading, 175.5, places=1)
        self.assertAlmostEqual(latest.speed, 1.4, places=1)

    def test_05_location_history_preservation(self):
        """Multiple location updates must append history records, never overwriting past records."""
        headers = {"Authorization": f"Bearer {self.token_a}"}
        initial_count = Location.query.filter_by(user_id=self.user_a.id).count()

        # Update 1
        self.client.post("/api/location/update", headers=headers, json={"latitude": 11.65601, "longitude": 76.62751})
        # Update 2
        self.client.post("/api/location/update", headers=headers, json={"latitude": 11.65602, "longitude": 76.62752})
        # Update 3
        self.client.post("/api/location/update", headers=headers, json={"latitude": 11.65603, "longitude": 76.62753})

        final_count = Location.query.filter_by(user_id=self.user_a.id).count()
        self.assertEqual(final_count, initial_count + 3, "Location history must be preserved, not overwritten")

    def test_06_shapely_correct_coordinate_order(self):
        """
        Verify Shapely Point-in-Polygon:
        GeoJSON stores coordinates as [longitude, latitude].
        Therefore, Shapely Point must be Point(longitude, latitude).
        """
        zone = ForestZone.query.filter_by(code="ZONE-SAFE-01").first()
        self.assertIsNotNone(zone, "ZONE-SAFE-01 must exist")
        poly = shape(zone.get_geojson())

        # Correct order: Point(longitude, latitude)
        lat = 11.65600
        lon = 76.62750
        correct_point = Point(lon, lat)
        self.assertTrue(poly.contains(correct_point), "Point(lon, lat) must be inside ZONE-SAFE-01")

        # Inverted order Point(lat, lon) is outside (11.656, 76.627 is near Africa/Equator!)
        inverted_point = Point(lat, lon)
        self.assertFalse(poly.contains(inverted_point), "Point(lat, lon) is inverted and must NOT match")

        # Test via GeofenceService
        res = GeofenceService.check_location_risk(lat, lon)
        self.assertTrue(res["in_zone"])
        self.assertEqual(res["zone_code"], "ZONE-SAFE-01")
        self.assertEqual(res["risk_level"], "LOW")

    def test_07_person_location_is_exact_gps_not_zone_centroid(self):
        """CRITICAL: The person's location must remain their exact GPS coordinate, NEVER zone centroid."""
        zone = ForestZone.query.filter_by(code="ZONE-MED-02").first()
        poly = shape(zone.get_geojson())
        centroid_lat = poly.centroid.y
        centroid_lon = poly.centroid.x

        # User is at a specific spot inside ZONE-MED-02, distinct from centroid
        user_gps_lat = 11.65800
        user_gps_lon = 76.64300

        # Ensure user coordinate is NOT the centroid
        self.assertNotEqual(user_gps_lat, centroid_lat)
        self.assertNotEqual(user_gps_lon, centroid_lon)

        headers = {"Authorization": f"Bearer {self.token_a}"}
        res = self.client.post("/api/location/update", headers=headers, json={
            "latitude": user_gps_lat,
            "longitude": user_gps_lon
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()["data"]

        # Returned location must be exact user GPS
        self.assertAlmostEqual(data["latitude"], user_gps_lat, places=5)
        self.assertAlmostEqual(data["longitude"], user_gps_lon, places=5)

        # Zone is identified as Pine Ridge Buffer Zone, but coordinates are NOT centroid
        self.assertEqual(data["zone_code"], "ZONE-MED-02")
        self.assertNotAlmostEqual(data["latitude"], centroid_lat, places=3)
        self.assertNotAlmostEqual(data["longitude"], centroid_lon, places=3)

    def test_08_current_location_endpoint_for_user(self):
        """GET /api/location/current must return the authenticated user's latest GPS position."""
        headers = {"Authorization": f"Bearer {self.token_a}"}

        # Send latest location
        latest_lat = 11.67500
        latest_lon = 76.62750
        self.client.post("/api/location/update", headers=headers, json={
            "latitude": latest_lat,
            "longitude": latest_lon,
            "accuracy": 3.8
        })

        res = self.client.get("/api/location/current", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()["data"]["location"]
        self.assertIsNotNone(data)
        self.assertEqual(data["user_id"], self.user_a.id)
        self.assertAlmostEqual(data["latitude"], latest_lat, places=5)
        self.assertAlmostEqual(data["longitude"], latest_lon, places=5)
        self.assertAlmostEqual(data["accuracy"], 3.8, places=1)
        self.assertEqual(data["zone_code"], "ZONE-HIGH-03")
        self.assertEqual(data["risk_level"], "HIGH")

    def test_09_multi_user_isolation_user_a_and_user_b(self):
        """User A and User B must maintain completely independent GPS coordinates."""
        headers_a = {"Authorization": f"Bearer {self.token_a}"}
        headers_b = {"Authorization": f"Bearer {self.token_b}"}

        # User A is in North Eco-Trail (LOW)
        lat_a = 11.65600
        lon_a = 76.62750
        self.client.post("/api/location/update", headers=headers_a, json={
            "latitude": lat_a,
            "longitude": lon_a,
            "accuracy": 5.0
        })

        # User B is in Blackwood Gorge (CRITICAL)
        lat_b = 11.68250
        lon_b = 76.65750
        self.client.post("/api/location/update", headers=headers_b, json={
            "latitude": lat_b,
            "longitude": lon_b,
            "accuracy": 8.0
        })

        # Check User A current location
        res_a = self.client.get("/api/location/current", headers=headers_a)
        loc_a = res_a.get_json()["data"]["location"]
        self.assertEqual(loc_a["user_id"], self.user_a.id)
        self.assertAlmostEqual(loc_a["latitude"], lat_a, places=5)
        self.assertAlmostEqual(loc_a["longitude"], lon_a, places=5)
        self.assertEqual(loc_a["risk_level"], "LOW")

        # Check User B current location
        res_b = self.client.get("/api/location/current", headers=headers_b)
        loc_b = res_b.get_json()["data"]["location"]
        self.assertEqual(loc_b["user_id"], self.user_b.id)
        self.assertAlmostEqual(loc_b["latitude"], lat_b, places=5)
        self.assertAlmostEqual(loc_b["longitude"], lon_b, places=5)
        self.assertEqual(loc_b["risk_level"], "CRITICAL")

        # Absolute coordinates must NOT be mixed
        self.assertNotEqual(loc_a["latitude"], loc_b["latitude"])
        self.assertNotEqual(loc_a["longitude"], loc_b["longitude"])

    def test_10_admin_current_locations_endpoint(self):
        """GET /api/admin/locations/current must return latest locations for all active users."""
        headers_admin = {"Authorization": f"Bearer {self.token_admin}"}
        res = self.client.get("/api/admin/locations/current", headers=headers_admin)
        self.assertEqual(res.status_code, 200)

        data = res.get_json()["data"]
        locations = data.get("locations", [])
        self.assertIsInstance(locations, list)

        # Should contain both User A and User B
        user_ids = [l["user_id"] for l in locations]
        self.assertIn(self.user_a.id, user_ids)
        self.assertIn(self.user_b.id, user_ids)

        # Check User A record
        user_a_loc = next(l for l in locations if l["user_id"] == self.user_a.id)
        self.assertEqual(user_a_loc["user_name"], "Rahul")

        # Check User B record
        user_b_loc = next(l for l in locations if l["user_id"] == self.user_b.id)
        self.assertEqual(user_b_loc["user_name"], "Priya")

    def test_11_socketio_broadcast_on_location_update(self):
        """POST /api/location/update must trigger NotificationService.broadcast_location_update."""
        headers = {"Authorization": f"Bearer {self.token_a}"}
        with patch("backend.app.services.NotificationService.broadcast_location_update") as mock_broadcast:
            res = self.client.post("/api/location/update", headers=headers, json={
                "latitude": 11.65650,
                "longitude": 76.62770,
                "accuracy": 4.0
            })
            self.assertEqual(res.status_code, 200)
            mock_broadcast.assert_called_once()
            call_arg = mock_broadcast.call_args[0][0]
            self.assertEqual(call_arg["user_id"], self.user_a.id)
            self.assertAlmostEqual(call_arg["latitude"], 11.65650, places=4)
            self.assertAlmostEqual(call_arg["longitude"], 76.62770, places=4)

    def test_12_sos_records_actual_device_gps_coordinates(self):
        """SOS trigger must store the actual device GPS coordinates, not zone center."""
        headers = {"Authorization": f"Bearer {self.token_a}"}
        sos_lat = 11.67540
        sos_lon = 76.62780

        res = self.client.post("/api/sos/trigger", headers=headers, json={
            "latitude": sos_lat,
            "longitude": sos_lon,
            "emergency_type": "WILD_ANIMAL",
            "message": "Encountered wild herd near trail"
        })
        self.assertEqual(res.status_code, 201)

        sos = SOSEvent.query.filter_by(user_id=self.user_a.id).order_by(SOSEvent.id.desc()).first()
        self.assertIsNotNone(sos)
        self.assertAlmostEqual(float(sos.latitude), sos_lat, places=5)
        self.assertAlmostEqual(float(sos.longitude), sos_lon, places=5)
        self.assertEqual(sos.emergency_type, "WILD_ANIMAL")


if __name__ == "__main__":
    unittest.main()
