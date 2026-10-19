import time
import unittest
from shapely.geometry import Point, Polygon
from backend.app import create_app
from backend.app.services.geofence_service import GeofenceService
from backend.app.services.visitor_service import (
    record_gps_update_with_geofence,
    db_conn,
    VISITOR_ZONE_STATE
)


class TestGeofenceService(unittest.TestCase):
    """Unit and integration tests for Geo-fencing & Point-in-Polygon detection."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app_context = cls.app.app_context()
        cls.app_context.push()

    @classmethod
    def tearDownClass(cls):
        cls.app_context.pop()

    def setUp(self):
        # Create a test visitor in SQLite for GPS testing
        with db_conn() as db:
            db.execute("DELETE FROM registrations WHERE unique_id = 'FOR-TEST-GEO-01'")
            db.execute("DELETE FROM locations WHERE unique_id = 'FOR-TEST-GEO-01'")
            db.execute("DELETE FROM events WHERE details LIKE '%FOR-TEST-GEO-01%'")
            db.execute("""
                INSERT INTO registrations (unique_id, name, phone, email, registered_at, status)
                VALUES ('FOR-TEST-GEO-01', 'Geo Test Visitor', '9876543210', 'geo@forest.gov', '2026-09-17 00:00:00', 'Active')
            """)
        if "FOR-TEST-GEO-01" in VISITOR_ZONE_STATE:
            del VISITOR_ZONE_STATE["FOR-TEST-GEO-01"]

    def tearDown(self):
        with db_conn() as db:
            db.execute("DELETE FROM registrations WHERE unique_id = 'FOR-TEST-GEO-01'")
            db.execute("DELETE FROM locations WHERE unique_id = 'FOR-TEST-GEO-01'")
            db.execute("DELETE FROM events WHERE details LIKE '%FOR-TEST-GEO-01%'")
        if "FOR-TEST-GEO-01" in VISITOR_ZONE_STATE:
            del VISITOR_ZONE_STATE["FOR-TEST-GEO-01"]

    def test_shapely_point_in_polygon_logic(self):
        """Test fundamental point-in-polygon logic with Shapely."""
        poly_coords = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        polygon = Polygon(poly_coords)

        inside_point = Point(5, 5)
        self.assertTrue(polygon.contains(inside_point))

        outside_point = Point(15, 15)
        self.assertFalse(polygon.contains(outside_point))

    def test_geofence_service_buffer_fallback(self):
        """Coordinates far outside forest zones should fall back to General Forest Buffer."""
        result = GeofenceService.check_location_risk(0.0, 0.0)
        self.assertFalse(result["in_zone"])
        self.assertEqual(result["zone_code"], "GENERAL-BUFFER")
        self.assertEqual(result["risk_level"], "LOW")
        self.assertFalse(result["is_restricted"])

    def test_get_all_active_zones_geojson(self):
        """Should return all active zones with valid GeoJSON structures."""
        zones = GeofenceService.get_all_active_zones_geojson()
        self.assertIsInstance(zones, list)
        self.assertGreater(len(zones), 0)
        for z in zones:
            self.assertIn("name", z)
            self.assertIn("risk_level", z)
            self.assertIn("geojson", z)
            self.assertIn("type", z["geojson"])
            self.assertEqual(z["geojson"]["type"], "Polygon")

    def test_zone_detection_with_first_zone_centroid(self):
        """Testing with the centroid of an existing active zone must detect that zone."""
        zones = GeofenceService.get_all_active_zones_geojson()
        self.assertGreater(len(zones), 0)
        first_zone = zones[0]
        coordinates = first_zone["geojson"]["coordinates"][0]

        poly = Polygon(coordinates)
        centroid = poly.centroid
        centroid_lon = centroid.x
        centroid_lat = centroid.y

        result = GeofenceService.check_location_risk(centroid_lat, centroid_lon)
        self.assertTrue(result["in_zone"])
        self.assertEqual(result["zone_name"], first_zone["name"])
        self.assertEqual(result["risk_level"], first_zone["risk_level"])

    def test_all_four_zone_detections(self):
        """Verify Shapely Point-in-Polygon detection for each distinct risk level zone."""
        # ZONE-SAFE-01: LOW Risk
        res_low = GeofenceService.check_location_risk(11.65600, 76.62750)
        self.assertTrue(res_low["in_zone"])
        self.assertEqual(res_low["zone_code"], "ZONE-SAFE-01")
        self.assertEqual(res_low["risk_level"], "LOW")
        self.assertFalse(res_low["is_restricted"])

        # ZONE-MED-02: MEDIUM Risk
        res_med = GeofenceService.check_location_risk(11.65900, 76.64500)
        self.assertTrue(res_med["in_zone"])
        self.assertEqual(res_med["zone_code"], "ZONE-MED-02")
        self.assertEqual(res_med["risk_level"], "MEDIUM")
        self.assertFalse(res_med["is_restricted"])

        # ZONE-HIGH-03: HIGH Risk
        res_high = GeofenceService.check_location_risk(11.67500, 76.62750)
        self.assertTrue(res_high["in_zone"])
        self.assertEqual(res_high["zone_code"], "ZONE-HIGH-03")
        self.assertEqual(res_high["risk_level"], "HIGH")
        self.assertTrue(res_high["is_restricted"])

        # ZONE-CRIT-04: CRITICAL Risk
        res_crit = GeofenceService.check_location_risk(11.68250, 76.65750)
        self.assertTrue(res_crit["in_zone"])
        self.assertEqual(res_crit["zone_code"], "ZONE-CRIT-04")
        self.assertEqual(res_crit["risk_level"], "CRITICAL")
        self.assertTrue(res_crit["is_restricted"])

    def test_outside_buffer_coordinate(self):
        """Coordinates well outside the park should fall back to General Buffer with LOW risk."""
        res_outside = GeofenceService.check_location_risk(12.50000, 77.50000)
        self.assertFalse(res_outside["in_zone"])
        self.assertEqual(res_outside["zone_code"], "GENERAL-BUFFER")
        self.assertEqual(res_outside["risk_level"], "LOW")
        self.assertFalse(res_outside["is_restricted"])

    def test_invalid_and_out_of_bounds_coordinates(self):
        """Verify out-of-bounds latitude/longitude and non-numeric inputs are rejected with clear errors."""
        res_lat_oor = record_gps_update_with_geofence("FOR-TEST-GEO-01", 95.0, 76.62750)
        self.assertFalse(res_lat_oor["success"])
        self.assertIn("out of bounds", res_lat_oor["error"].lower())

        res_lon_oor = record_gps_update_with_geofence("FOR-TEST-GEO-01", 11.65600, 185.0)
        self.assertFalse(res_lon_oor["success"])
        self.assertIn("out of bounds", res_lon_oor["error"].lower())

        res_none = record_gps_update_with_geofence("FOR-TEST-GEO-01", None, None)
        self.assertFalse(res_none["success"])

        res_invalid = record_gps_update_with_geofence("FOR-TEST-GEO-01", "invalid_lat", 76.62750)
        self.assertFalse(res_invalid["success"])

    def test_gps_update_history_and_profile_sync(self):
        """Verify record_gps_update_with_geofence updates registration record and logs location history."""
        res = record_gps_update_with_geofence(
            unique_id="FOR-TEST-GEO-01",
            latitude=11.65600,
            longitude=76.62750,
            accuracy=4.5
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["zone_code"], "ZONE-SAFE-01")
        self.assertEqual(res["risk_level"], "LOW")
        self.assertFalse(res["alert_triggered"])

        # Check registrations table
        with db_conn(True) as db:
            reg = db.execute("SELECT * FROM registrations WHERE unique_id = 'FOR-TEST-GEO-01'").fetchone()
            self.assertIsNotNone(reg)
            self.assertAlmostEqual(reg["latitude"], 11.65600, places=4)
            self.assertAlmostEqual(reg["longitude"], 76.62750, places=4)
            self.assertEqual(reg["current_zone"], "North Visitor Eco-Trail")
            self.assertEqual(reg["risk_level"], "LOW")
            self.assertEqual(reg["gps_status"], "Active")

            # Check locations history table
            locs = db.execute(
                "SELECT * FROM locations WHERE unique_id = 'FOR-TEST-GEO-01' ORDER BY id DESC"
            ).fetchall()
            self.assertGreaterEqual(len(locs), 1)
            self.assertAlmostEqual(locs[0]["latitude"], 11.65600, places=4)
            self.assertAlmostEqual(locs[0]["longitude"], 76.62750, places=4)
            self.assertAlmostEqual(locs[0]["accuracy"], 4.5, places=1)

    def test_state_transition_and_restricted_alert(self):
        """Moving from LOW risk zone to HIGH risk zone must trigger an alert event."""
        # 1. First update in LOW zone
        record_gps_update_with_geofence("FOR-TEST-GEO-01", 11.65600, 76.62750, accuracy=5.0)

        # 2. Transition into HIGH zone
        res_transition = record_gps_update_with_geofence(
            "FOR-TEST-GEO-01", 11.67500, 76.62750, accuracy=3.0
        )
        self.assertTrue(res_transition["success"])
        self.assertEqual(res_transition["risk_level"], "HIGH")
        self.assertTrue(res_transition["alert_triggered"])
        self.assertIn("HIGH Risk Zone", res_transition["alert_details"])

        # 3. Verify event recorded in DB
        with db_conn(True) as db:
            evt = db.execute(
                "SELECT * FROM events WHERE details LIKE '%FOR-TEST-GEO-01%' ORDER BY id DESC"
            ).fetchone()
            self.assertIsNotNone(evt)
            self.assertEqual(evt["event_type"], "GEOFENCE_RESTRICTED_ALERT")
            self.assertEqual(evt["zone"], "HIGH")

    def test_alert_cooldown_suppression(self):
        """Repeated GPS reports in restricted zone within 15 seconds must not spam duplicate alerts."""
        # 1. First restricted update triggers alert
        res1 = record_gps_update_with_geofence("FOR-TEST-GEO-01", 11.68250, 76.65750, accuracy=2.0)
        self.assertTrue(res1["success"])
        self.assertTrue(res1["alert_triggered"])

        # 2. Immediate second update (0.1s later) must be throttled
        time.sleep(0.1)
        res2 = record_gps_update_with_geofence("FOR-TEST-GEO-01", 11.68260, 76.65760, accuracy=2.1)
        self.assertTrue(res2["success"])
        self.assertEqual(res2["risk_level"], "CRITICAL")
        self.assertFalse(res2["alert_triggered"], "Cooldown failed: duplicate alert was emitted within 15s")


if __name__ == "__main__":
    unittest.main()
