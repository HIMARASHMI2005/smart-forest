from backend.app.extensions import socketio

class NotificationService:
    """Dispatches real-time WebSocket events via Socket.IO."""

    @staticmethod
    def broadcast_alert(alert_data: dict):
        """Emits new alert to admin command center and active sessions."""
        try:
            socketio.emit("new_alert", alert_data)
            print(f"[SocketIO] Broadcasted alert: {alert_data.get('alert_type')}")
        except Exception as e:
            print(f"[SocketIO Broadcast Alert Error]: {e}")

    @staticmethod
    def broadcast_sos(sos_data: dict):
        """Emits emergency SOS event with highest priority."""
        try:
            socketio.emit("sos_triggered", sos_data)
            print(f"[SocketIO] Broadcasted SOS Event from User: {sos_data.get('user_name')}")
        except Exception as e:
            print(f"[SocketIO Broadcast SOS Error]: {e}")

    @staticmethod
    def broadcast_detection(detection_data: dict):
        """Emits live detection update."""
        try:
            socketio.emit("new_detection", detection_data)
        except Exception as e:
            print(f"[SocketIO Broadcast Detection Error]: {e}")

    @staticmethod
    def broadcast_risk_update(risk_data: dict):
        """Emits risk level change."""
        try:
            socketio.emit("risk_update", risk_data)
        except Exception as e:
            print(f"[SocketIO Broadcast Risk Error]: {e}")

    @staticmethod
    def broadcast_location_update(location_data: dict):
        """Emits real-time GPS location update for a registered person."""
        try:
            socketio.emit("location_update", location_data)
            print(f"[SocketIO] Broadcasted location_update for user: {location_data.get('user_id')} ({location_data.get('name')})")
        except Exception as e:
            print(f"[SocketIO Broadcast Location Error]: {e}")

