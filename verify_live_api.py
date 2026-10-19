import requests
import cv2
import base64
import numpy as np

BASE_URL = "http://127.0.0.1:5000"

print("=" * 60)
print("LIVE API END-TO-END VERIFICATION")
print("=" * 60)

# 1. Check /api/config
cfg = requests.get(f"{BASE_URL}/api/config").json()
print("1. Config API:", cfg)
assert cfg.get("face_match_threshold") == 0.60

# 2. Register Ranger Priya via /api/register
img_priya = cv2.imread("dataset/faces/ranger_priya/face_01.jpg")
_, enc_p = cv2.imencode(".jpg", img_priya)
b64_priya = "data:image/jpeg;base64," + base64.b64encode(enc_p).decode("utf-8")

reg_resp = requests.post(f"{BASE_URL}/api/register", json={
    "name": "Ranger Priya",
    "phone": "9876543210",
    "email": "priya@forest.gov.in",
    "face_image": b64_priya
}).json()
print("\n2. Registration Response:", reg_resp)
assert reg_resp.get("success") is True
assert reg_resp.get("face_registered") is True
priya_uid = reg_resp.get("unique_id")

# 3. Test detection on Priya webcam portrait
p2 = cv2.imread("dataset/faces/ranger_priya/face_02.jpg")
frame_priya = np.ones((480, 640, 3), dtype=np.uint8) * 180
# Natural body/clothing background
frame_priya[220:480, 160:480] = (50, 45, 40)
frame_priya[100:260, 240:400] = cv2.resize(p2, (160, 160))
_, enc_fp = cv2.imencode(".jpg", frame_priya)

det1 = requests.post(f"{BASE_URL}/api/detect", files={
    "frame": ("frame.jpg", enc_fp.tobytes(), "image/jpeg")
}).json()
print("\n3. Live Detection - Priya Portrait:")
for p in det1.get("people", []):
    print("  ", p)
priya_matched = [p for p in det1.get("people", []) if p.get("visitor_name") == "Ranger Priya"]
assert len(priya_matched) == 1, f"Expected 1 Priya match, got: {priya_matched}"
assert priya_matched[0]["status"] == "REGISTERED"
assert priya_matched[0]["match_confidence"] >= 0.85
print("   [SUCCESS] Priya correctly identified with confidence:", priya_matched[0]["match_confidence"])

# 4. Test detection on unregistered person (Sharma)
s1 = cv2.imread("dataset/faces/ranger_sharma/face_01.jpg")
frame_sharma = np.ones((480, 640, 3), dtype=np.uint8) * 180
frame_sharma[220:480, 160:480] = (50, 45, 40)
frame_sharma[100:260, 240:400] = cv2.resize(s1, (160, 160))
_, enc_fs = cv2.imencode(".jpg", frame_sharma)

det2 = requests.post(f"{BASE_URL}/api/detect", files={
    "frame": ("frame.jpg", enc_fs.tobytes(), "image/jpeg")
}).json()
print("\n4. Live Detection - Unregistered Sharma Portrait:")
for p in det2.get("people", []):
    print("  ", p)
sharma_priya_matches = [p for p in det2.get("people", []) if p.get("visitor_name") == "Ranger Priya"]
assert len(sharma_priya_matches) == 0, f"Unregistered person falsely matched as Priya: {sharma_priya_matches}"
for p in det2.get("people", []):
    assert p["status"] == "UNREGISTERED"
    assert p["visitor_name"] == "UNREGISTERED"
    assert p["match_confidence"] == 0.0
print("   [SUCCESS] Unregistered person strictly labeled UNREGISTERED with 0.0 confidence")

# 5. Test group frame (Priya + Sharma + Deepa)
d1 = cv2.imread("dataset/faces/visitor_deepa/face_01.jpg")
frame_group = np.ones((480, 640, 3), dtype=np.uint8) * 180
frame_group[200:480, 40:200]   = (45, 55, 45)
frame_group[200:480, 240:400]  = (50, 45, 40)
frame_group[200:480, 440:600]  = (40, 45, 55)
frame_group[90:230, 60:180]   = cv2.resize(p2, (120, 140))
frame_group[90:230, 260:380]  = cv2.resize(s1, (120, 140))
frame_group[90:230, 460:580]  = cv2.resize(d1, (120, 140))
_, enc_fg = cv2.imencode(".jpg", frame_group)

# 5. Live Detection - Group Frame (Priya + Sharma + Deepa)
try:
    det3 = requests.post(f"{BASE_URL}/api/detect", files={
        "frame": ("frame.jpg", enc_fg.tobytes(), "image/jpeg")
    }).json()
    print("\n5. Live Detection - Group Frame (Priya + Sharma + Deepa):")
    for p in det3.get("people", []):
        print("  ", p)

    group_people = det3.get("people", [])
    priya_in_group = [p for p in group_people if p.get("visitor_name") == "Ranger Priya"]

    assert len(priya_in_group) == 1, f"Expected exactly 1 Priya in group, got: {len(priya_in_group)}"
    assert priya_in_group[0]["status"] == "REGISTERED"
    assert priya_in_group[0]["match_confidence"] >= 0.85

    non_priya = [p for p in group_people if p.get("visitor_name") != "Ranger Priya"]
    assert len(non_priya) >= 2, f"Expected at least 2 non-Priya targets in group, got: {len(non_priya)}"

    print(f"   [SUCCESS] Group identification accurate: exactly 1 Priya ({priya_in_group[0]['match_confidence']}) and {len(non_priya)} other targets.")
finally:
    # 6. Cleanup test visitor
    del_resp = requests.delete(f"{BASE_URL}/api/visitor/{priya_uid}").json()
    assert del_resp.get("success") is True, f"Cleanup failed: {del_resp}"
    print(f"\n6. Cleanup: Successfully deleted test visitor {priya_uid} from database and disk.")

print("\n" + "=" * 60)
print("ALL LIVE API VERIFICATION TESTS PASSED PERFECTLY!")
print("=" * 60)
