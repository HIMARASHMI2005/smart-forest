from typing import Optional, Dict, Any, List
from shapely.geometry import Point, Polygon, shape
import json
from backend.app.models.zone import ForestZone

class GeofenceService:
    """Evaluates GPS coordinates against Forest Zone polygon boundaries."""

    @staticmethod
    def get_zone_for_coordinates(lat: float, lon: float) -> Optional[ForestZone]:
        """
        Performs Point-in-Polygon check for given GPS coordinates.
        Note: GeoJSON coordinates are in [longitude, latitude] format.
        """
        if lat is None or lon is None:
            return None

        point = Point(float(lon), float(lat))
        zones = ForestZone.query.filter_by(is_active=True).all()

        for zone in zones:
            try:
                geojson_data = zone.get_geojson()
                if not geojson_data:
                    continue
                
                polygon = shape(geojson_data)
                if polygon.contains(point) or polygon.touches(point):
                    return zone
            except Exception as e:
                print(f"[GeofenceService Error parsing zone {zone.id}]: {e}")
                continue

        return None

    @staticmethod
    def check_location_risk(lat: float, lon: float) -> Dict[str, Any]:
        """Returns zone details and risk level for a coordinate."""
        zone = GeofenceService.get_zone_for_coordinates(lat, lon)
        if zone:
            return {
                "in_zone": True,
                "zone_id": zone.id,
                "zone_name": zone.name,
                "zone_code": zone.code,
                "risk_level": zone.risk_level,
                "description": zone.description,
                "is_restricted": zone.risk_level in ["HIGH", "CRITICAL"]
            }
        
        return {
            "in_zone": False,
            "zone_id": None,
            "zone_name": "General Forest Buffer",
            "zone_code": "GENERAL-BUFFER",
            "risk_level": "LOW",
            "description": "Perimeter outside designated critical zones.",
            "is_restricted": False
        }

    @staticmethod
    def get_all_active_zones_geojson() -> List[Dict[str, Any]]:
        """Returns list of all active forest zones formatted for Leaflet."""
        zones = ForestZone.query.filter_by(is_active=True).all()
        result = []
        for z in zones:
            result.append({
                "id": z.id,
                "name": z.name,
                "code": z.code,
                "risk_level": z.risk_level,
                "description": z.description,
                "geojson": z.get_geojson()
            })
        return result
