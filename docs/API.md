# Smart Forest Geo-Fencing & Emergency Monitoring System
# Complete REST & Socket.IO API Specification

## 1. Overview
The backend provides a secure REST API (JSON payloads, JWT Bearer authentication) and a bidirectional real-time WebSocket layer via Flask-SocketIO for immediate emergency alert dispatching and live telemetry streaming.

- **Base URL**: `http://127.0.0.1:5000`
- **Authentication**: `Authorization: Bearer <jwt_access_token>`
- **Response Format**: `{"success": bool, "message": str, "data": dict}`

---

## 2. Authentication API (`/api/auth`)

### 2.1 User Registration
- **Endpoint**: `POST /api/auth/register`
- **Auth Required**: No
- **Request Body**:
```json
{
  "name": "Ranger Priya",
  "email": "priya@forest.gov",
  "phone": "+919876543210",
  "password": "SecurePassword2026!",
  "emergency_contact": "+919123456789"
}
```
- **Responses**:
  - `201 Created`: User registered successfully.
  - `400 Bad Request`: Missing required fields or password < 6 characters.
  - `409 Conflict`: Email address already in use.

### 2.2 User Login
- **Endpoint**: `POST /api/auth/login`
- **Auth Required**: No
- **Request Body**:
```json
{
  "email": "priya@forest.gov",
  "password": "SecurePassword2026!"
}
```
- **Response `200 OK`**:
```json
{
  "success": true,
  "message": "Login successful.",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "user": {
      "id": 1,
      "name": "Ranger Priya",
      "email": "priya@forest.gov",
      "role": "USER",
      "emergency_contact": "+919123456789"
    }
  }
}
```

### 2.3 Current User Info
- **Endpoint**: `GET /api/auth/me`
- **Auth Required**: Yes (`Bearer <token>`)
- **Response `200 OK`**: Returns authenticated user profile.

---

## 3. Real-Time AI Computer Vision API (`/api/ai`)

### 3.1 Live Video Frame Detection & Person Identification
Processes raw webcam or drone camera frames, executes `ForestPersonNet` person detection and `ForestFaceNet` face metric identification, applies `EmergencyRiskEngine`, and broadcasts critical events.

- **Endpoint**: `POST /api/ai/detect_frame`
- **Auth Required**: Optional (Public monitor) / Recommended
- **Request Body**:
```json
{
  "frame": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQ...",
  "latitude": 11.6854,
  "longitude": 76.1245
}
```
- **Response `200 OK`**:
```json
{
  "success": true,
  "data": {
    "person_count": 2,
    "detections": [
      {
        "bbox": [120, 85, 210, 310],
        "normalized_bbox": [0.1875, 0.1771, 0.3281, 0.6458],
        "confidence": 0.892,
        "class": "person"
      }
    ],
    "identity": {
      "matched": true,
      "user_name": "Ranger Priya",
      "confidence": 0.884,
      "status": "AUTHORIZED"
    },
    "risk_assessment": {
      "score": 15,
      "level": "LOW",
      "color": "#2a9d8f",
      "action": "Normal operating conditions. Routine automated monitoring."
    }
  }
}
```

### 3.2 Live Face Registration
Registers a user's face profile directly from webcam captures, computing and storing their 128-dimensional normalized embedding in the database.

- **Endpoint**: `POST /api/ai/register_face`
- **Auth Required**: Yes (`Bearer <token>`)
- **Request Body**:
```json
{
  "face_samples": [
    "data:image/jpeg;base64,...",
    "data:image/jpeg;base64,...",
    "data:image/jpeg;base64,...",
    "data:image/jpeg;base64,...",
    "data:image/jpeg;base64,..."
  ]
}
```
- **Response `200 OK`**: Face profile registered with calculated 128-D centroid.

### 3.3 AI Subsystem Status
- **Endpoint**: `GET /api/ai/status`
- **Response `200 OK`**: Returns model file paths, training status, and device architecture.

---

## 4. Geo-Fencing & Boundary API (`/api/geofence`)

### 4.1 Get All Active Forest Zones
- **Endpoint**: `GET /api/geofence/zones`
- **Response `200 OK`**: Returns GeoJSON polygons of core forest zones, buffer corridors, and danger sectors formatted for Leaflet.

### 4.2 Point-in-Polygon Coordinate Risk Check
- **Endpoint**: `POST /api/geofence/check_location`
- **Request Body**:
```json
{
  "latitude": 11.6854,
  "longitude": 76.1245
}
```
- **Response `200 OK`**:
```json
{
  "success": true,
  "data": {
    "in_zone": true,
    "zone_name": "Wildlife Sanctuary Core Zone",
    "zone_code": "WILDLIFE-CORE-01",
    "risk_level": "HIGH",
    "is_restricted": true,
    "description": "Restricted habitat with active elephant & tiger corridors."
  }
}
```

---

## 5. Emergency SOS API (`/api/sos`)

### 5.1 Trigger Emergency SOS
- **Endpoint**: `POST /api/sos/trigger`
- **Auth Required**: Yes
- **Request Body**:
```json
{
  "latitude": 11.6854,
  "longitude": 76.1245,
  "emergency_type": "WILD_ANIMAL",
  "message": "Aggressive elephant spotted near trail marker 14"
}
```
- **Response `201 Created`**:
```json
{
  "success": true,
  "message": "Emergency SOS broadcasted! Rescue units notified.",
  "data": {
    "sos_id": 42,
    "status": "ACTIVE",
    "risk_score": 100,
    "risk_level": "CRITICAL"
  }
}
```

### 5.2 List Active Emergencies
- **Endpoint**: `GET /api/sos/active`
- **Auth Required**: Yes (Rangers / Admins)

---

## 6. Socket.IO Real-Time Event Protocol

### 6.1 Server-to-Client Events
- **`new_alert`**: Broadcast whenever risk engine score triggers MEDIUM, HIGH, or CRITICAL alert.
- **`sos_broadcast`**: High-priority alarm emitted immediately upon any user SOS activation with GPS coordinates.
- **`live_detection`**: Real-time bounding box and telemetry updates streamed to Admin Live Monitor.
- **`system_notification`**: General broadcast notifications (weather warnings, sector closures).
