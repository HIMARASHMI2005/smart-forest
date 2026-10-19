-- ==========================================================
-- SMART FOREST GEO-FENCING & EMERGENCY MONITORING SYSTEM
-- Initial Seed Data (Users, Forest Zones, Alert Profiles)
-- ==========================================================

USE `smart_forest_db`;

-- 1. Insert Initial Users
-- Passwords:
-- admin@smartforest.org / Admin@123  (Role: ADMIN)
-- ranger.john@smartforest.org / User@123 (Role: USER)
-- ranger.elena@smartforest.org / User@123 (Role: USER)
-- hiker.david@gmail.com / User@123 (Role: USER)

INSERT INTO `users` (`id`, `forest_user_id`, `name`, `email`, `phone`, `password_hash`, `role`, `emergency_contact`, `status`) VALUES
(1, 'FOR-AD0001', 'Chief Warden Sharma', 'admin@smartforest.org', '+91 9876543210', '$2b$12$A29hd1lGc8lErBCADxEaH.OOGxOvzJLNtxzxwUddYpE2zvTnUVFBm', 'ADMIN', '+91 9876500000', 'ACTIVE'),
(2, 'FOR-RN0002', 'Ranger John Doe', 'ranger.john@smartforest.org', '+91 9876543211', '$2b$12$34L.gl266xHQ8oayHylbsu8OlhzUq6KYotaHP4TAoMYHvJxx0C.Z.', 'USER', '+91 9876500001', 'ACTIVE'),
(3, 'FOR-RN0003', 'Ranger Elena Rostova', 'ranger.elena@smartforest.org', '+91 9876543212', '$2b$12$34L.gl266xHQ8oayHylbsu8OlhzUq6KYotaHP4TAoMYHvJxx0C.Z.', 'USER', '+91 9876500002', 'ACTIVE'),
(4, 'FOR-VI0004', 'David Miller (Visitor)', 'hiker.david@gmail.com', '+91 9876543213', '$2b$12$34L.gl266xHQ8oayHylbsu8OlhzUq6KYotaHP4TAoMYHvJxx0C.Z.', 'USER', '+91 9876500003', 'ACTIVE')
ON DUPLICATE KEY UPDATE `name` = VALUES(`name`), `forest_user_id` = VALUES(`forest_user_id`);

-- 2. Insert Forest Zones with GeoJSON Polygon Coordinates
-- Sample center around Nilgiri / Bandipur Forest Reserve region (lat: ~11.65, lon: ~76.62)
INSERT INTO `forest_zones` (`id`, `name`, `code`, `boundary_geojson`, `risk_level`, `description`, `is_active`) VALUES
(1, 'North Visitor Basecamp & Eco-Trail', 'ZONE-SAFE-01', 
JSON_OBJECT(
    'type', 'Polygon',
    'coordinates', JSON_ARRAY(JSON_ARRAY(
        JSON_ARRAY(76.6200, 11.6500),
        JSON_ARRAY(76.6350, 11.6500),
        JSON_ARRAY(76.6350, 11.6620),
        JSON_ARRAY(76.6200, 11.6620),
        JSON_ARRAY(76.6200, 11.6500)
    ))
), 'LOW', 'Authorized tourism and visitor recreational trail with warden monitoring.', 1),

(2, 'Pine Ridge Sector B - Buffer Zone', 'ZONE-MED-02', 
JSON_OBJECT(
    'type', 'Polygon',
    'coordinates', JSON_ARRAY(JSON_ARRAY(
        JSON_ARRAY(76.6350, 11.6500),
        JSON_ARRAY(76.6550, 11.6500),
        JSON_ARRAY(76.6550, 11.6680),
        JSON_ARRAY(76.6350, 11.6680),
        JSON_ARRAY(76.6350, 11.6500)
    ))
), 'MEDIUM', 'Semi-dense terrain with moderate elevation and restricted night-time access.', 1),

(3, 'Wild Elephant & Predator Corridor', 'ZONE-HIGH-03', 
JSON_OBJECT(
    'type', 'Polygon',
    'coordinates', JSON_ARRAY(JSON_ARRAY(
        JSON_ARRAY(76.6150, 11.6650),
        JSON_ARRAY(76.6400, 11.6650),
        JSON_ARRAY(76.6400, 11.6850),
        JSON_ARRAY(76.6150, 11.6850),
        JSON_ARRAY(76.6150, 11.6650)
    ))
), 'HIGH', 'Active wildlife movement zone. Unaccompanied entry strictly prohibited.', 1),

(4, 'Blackwood Gorge & Cliff Area', 'ZONE-CRIT-04', 
JSON_OBJECT(
    'type', 'Polygon',
    'coordinates', JSON_ARRAY(JSON_ARRAY(
        JSON_ARRAY(76.6450, 11.6700),
        JSON_ARRAY(76.6700, 11.6700),
        JSON_ARRAY(76.6700, 11.6950),
        JSON_ARRAY(76.6450, 11.6950),
        JSON_ARRAY(76.6450, 11.6700)
    ))
), 'CRITICAL', 'Hazardous terrain, unstable cliffs, and active poacher monitoring perimeter.', 1)
ON DUPLICATE KEY UPDATE `name` = VALUES(`name`);

-- 3. Insert Initial System Logs
INSERT INTO `system_logs` (`event_type`, `details`, `timestamp`) VALUES
('SYSTEM_INIT', 'Smart Forest Geo-Fencing & Emergency Monitoring System database initialized.', NOW()),
('SECURITY_AUDIT', 'Role-based access control and bcrypt encryption verified.', NOW()),
('ZONES_CONFIGURED', '4 Geo-Fenced forest security sectors initialized.', NOW());

-- 4. Insert Initial Sample Alerts for Dashboard Demo
INSERT INTO `alerts` (`id`, `alert_type`, `severity`, `user_id`, `zone_id`, `latitude`, `longitude`, `message`, `status`, `created_at`) VALUES
(1, 'GEOFENCE_WARNING', 'MEDIUM', 2, 2, 11.65500000, 76.64000000, 'Ranger John entered Buffer Zone (Pine Ridge Sector B).', 'ACKNOWLEDGED', NOW() - INTERVAL 1 HOUR),
(2, 'UNKNOWN_PERSON', 'HIGH', NULL, 3, 11.67200000, 76.62500000, 'Unidentified individual detected in Wild Elephant Corridor without authorization badge.', 'ACTIVE', NOW() - INTERVAL 25 MINUTE);
