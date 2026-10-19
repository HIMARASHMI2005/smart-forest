from datetime import datetime
from typing import Dict, Any, List

class EmergencyRiskEngine:
    """
    Transparent rule-based risk evaluation engine combining:
    1. Geo-fence zone risk classification
    2. Real-time AI detection events (unknown persons, group size)
    3. Emergency SOS status
    4. Environmental & temporal factors (night hours, repeat violations)
    """

    @staticmethod
    def evaluate_risk(
        zone_risk_level: str = "LOW",
        is_unknown_person: bool = False,
        person_count: int = 1,
        is_sos_active: bool = False,
        user_role: str = "USER",
        custom_time: datetime = None
    ) -> Dict[str, Any]:
        
        current_time = custom_time if custom_time else datetime.now()
        current_hour = current_time.hour
        is_night_time = (current_hour >= 18 or current_hour < 6)

        score = 0
        triggered_rules: List[str] = []

        # 1. Critical Override: SOS Event
        if is_sos_active:
            return {
                "score": 100,
                "level": "CRITICAL",
                "triggered_rules": ["EMERGENCY_SOS_TRIGGERED (Immediate Critical Priority)"],
                "color": "#e63946",
                "recommended_action": "Dispatch emergency rescue team to GPS coordinates immediately."
            }

        # 2. Zone Base Risk Contribution
        zone_scores = {
            "LOW": 5,
            "MEDIUM": 25,
            "HIGH": 55,
            "CRITICAL": 80
        }
        base_zone_score = zone_scores.get(zone_risk_level.upper(), 5)
        score += base_zone_score
        triggered_rules.append(f"Zone Risk Base Factor: {zone_risk_level} (+{base_zone_score} pts)")

        # 3. AI Unknown Person Rule
        if is_unknown_person:
            score += 30
            triggered_rules.append("AI Detection: Unidentified individual detected in monitored perimeter (+30 pts)")

        # 4. Crowd / Person Count Factor in Restricted Zones
        if person_count > 3:
            if zone_risk_level in ["HIGH", "CRITICAL"]:
                score += 25
                triggered_rules.append(f"Unusual Group Gathering: {person_count} persons detected in {zone_risk_level} zone (+25 pts)")
            else:
                score += 10
                triggered_rules.append(f"Group Gathering: {person_count} persons detected (+10 pts)")

        # 5. Temporal / Night Hours Factor
        if is_night_time:
            score += 15
            triggered_rules.append(f"Temporal Factor: Monitored during nocturnal restricted hours ({current_hour:02d}:00) (+15 pts)")

        # 6. Unregistered visitor in high risk zone
        if user_role != "ADMIN" and zone_risk_level in ["HIGH", "CRITICAL"] and is_unknown_person:
            score += 15
            triggered_rules.append("Security Violation: Unregistered personnel traversing high-threat wildlife/cliff sector (+15 pts)")

        # Cap score between 0 and 100
        score = max(0, min(100, score))

        # Determine composite level
        if score >= 75:
            level = "CRITICAL"
            color = "#e63946"
            action = "Sound alarm, notify command center, dispatch nearest ranger patrol."
        elif score >= 50:
            level = "HIGH"
            color = "#f77f00"
            action = "Issue verbal warning, monitor video stream closely, verify personnel credentials."
        elif score >= 25:
            level = "MEDIUM"
            color = "#fcbf49"
            action = "Log location breadcrumbs, monitor zone boundary proximity."
        else:
            level = "LOW"
            color = "#2a9d8f"
            action = "Normal operating conditions. Routine automated monitoring."

        return {
            "score": score,
            "level": level,
            "color": color,
            "triggered_rules": triggered_rules,
            "recommended_action": action,
            "timestamp": current_time.strftime("%Y-%m-%d %H:%M:%S")
        }
