import unittest
from datetime import datetime
from backend.app.services.risk_engine import EmergencyRiskEngine

class TestEmergencyRiskEngine(unittest.TestCase):
    """Unit tests for the rule-based emergency risk evaluation engine."""

    def test_sos_active_override(self):
        """SOS trigger must immediately produce a score of 100 with CRITICAL level."""
        result = EmergencyRiskEngine.evaluate_risk(
            zone_risk_level="LOW",
            is_unknown_person=False,
            person_count=1,
            is_sos_active=True
        )
        self.assertEqual(result["score"], 100)
        self.assertEqual(result["level"], "CRITICAL")
        self.assertIn("EMERGENCY_SOS_TRIGGERED", result["triggered_rules"][0])

    def test_low_risk_daytime_known_user(self):
        """A registered user in LOW risk zone during daytime should have LOW risk."""
        daytime = datetime(2026, 9, 16, 12, 0, 0)
        result = EmergencyRiskEngine.evaluate_risk(
            zone_risk_level="LOW",
            is_unknown_person=False,
            person_count=1,
            is_sos_active=False,
            user_role="USER",
            custom_time=daytime
        )
        self.assertEqual(result["level"], "LOW")
        self.assertLess(result["score"], 25)

    def test_medium_risk_zone(self):
        """MEDIUM zone during daytime with single known person."""
        daytime = datetime(2026, 9, 16, 14, 0, 0)
        result = EmergencyRiskEngine.evaluate_risk(
            zone_risk_level="MEDIUM",
            is_unknown_person=False,
            person_count=1,
            custom_time=daytime
        )
        # Base zone score for MEDIUM is 25
        self.assertEqual(result["score"], 25)
        self.assertEqual(result["level"], "MEDIUM")

    def test_unknown_person_penalty(self):
        """Unidentified person adds +30 pts to base risk."""
        daytime = datetime(2026, 9, 16, 12, 0, 0)
        result_known = EmergencyRiskEngine.evaluate_risk(
            zone_risk_level="LOW",
            is_unknown_person=False,
            custom_time=daytime
        )
        result_unknown = EmergencyRiskEngine.evaluate_risk(
            zone_risk_level="LOW",
            is_unknown_person=True,
            custom_time=daytime
        )
        self.assertEqual(result_unknown["score"] - result_known["score"], 30)

    def test_high_risk_zone_with_gathering(self):
        """Multiple unknown persons in a HIGH risk zone."""
        daytime = datetime(2026, 9, 16, 12, 0, 0)
        result = EmergencyRiskEngine.evaluate_risk(
            zone_risk_level="HIGH",
            is_unknown_person=True,
            person_count=5,
            custom_time=daytime
        )
        # 55 (HIGH base) + 30 (unknown) + 25 (group > 3 in HIGH) + 15 (unregistered in HIGH) = 125 -> capped at 100
        self.assertEqual(result["score"], 100)
        self.assertEqual(result["level"], "CRITICAL")

    def test_night_time_factor(self):
        """Nighttime hours (>= 18:00 or < 06:00) should increase risk score by +15 pts."""
        daytime = datetime(2026, 9, 16, 12, 0, 0)
        nighttime = datetime(2026, 9, 16, 22, 0, 0)

        result_day = EmergencyRiskEngine.evaluate_risk(
            zone_risk_level="LOW",
            is_unknown_person=False,
            custom_time=daytime
        )
        result_night = EmergencyRiskEngine.evaluate_risk(
            zone_risk_level="LOW",
            is_unknown_person=False,
            custom_time=nighttime
        )
        self.assertEqual(result_night["score"] - result_day["score"], 15)

if __name__ == "__main__":
    unittest.main()
