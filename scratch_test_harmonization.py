import cv2
import numpy as np
from ai.person_detection.inference import ForestPersonDetector
from ai.face_identification.inference import ForestFaceIdentifier
from backend.app.services.visitor_service import db_conn, reload_embeddings_cache, REGISTERED_EMBEDDINGS_CACHE

detector = ForestPersonDetector()
identifier = ForestFaceIdentifier()

# Load Priya from dataset and register into database
p1 = cv2.imread('dataset/faces/ranger_priya/face_01.jpg')
p2 = cv2.imread('dataset/faces/ranger_priya/face_02.jpg')

# Webcam portrait frame of Priya
frame_bgr = np.zeros((480, 640, 3), dtype=np.uint8)
frame_bgr[200:480, 160:480] = (80, 90, 70)
face_resized = cv2.resize(p2, (180, 180))
frame_bgr[100:280, 230:410] = face_resized

h, w = frame_bgr.shape[:2]
cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
gray_frame = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
global_faces = cascade.detectMultiScale(gray_frame, scaleFactor=1.1, minNeighbors=3, minSize=(30, 30))

det_result = detector.detect(frame_bgr)
raw_boxes = [d['bbox'] for d in det_result.get('detections', [])]

print('Raw boxes from detector:', raw_boxes)
print('Global faces found:', len(global_faces), global_faces)

# Perform Face-Person Harmonization
targets = []
used_faces = set()

# For each detected face, find or construct the person bounding box
for f_idx, (fx, fy, fw, fh) in enumerate(global_faces):
    fcx = fx + fw / 2.0
    fcy = fy + fh / 2.0
    
    # Check if any raw box overlaps with this face
    overlapping = []
    for b_idx, (bx1, by1, bx2, by2) in enumerate(raw_boxes):
        # Horizontal overlap with face
        x_left = max(bx1, fx)
        x_right = min(bx2, fx + fw)
        bw = bx2 - bx1
        if (x_right - x_left) > 0.3 * min(bw, fw):
            overlapping.append(b_idx)
            
    if overlapping:
        # Merge overlapping boxes with face
        all_x1 = min([raw_boxes[bi][0] for bi in overlapping] + [fx - int(fw * 0.25)])
        all_y1 = min([raw_boxes[bi][1] for bi in overlapping] + [fy - int(fh * 0.15)])
        all_x2 = max([raw_boxes[bi][2] for bi in overlapping] + [fx + fw + int(fw * 0.25)])
        all_y2 = max([raw_boxes[bi][3] for bi in overlapping] + [fy + fh + int(fh * 2.5)])
        box = [max(0, all_x1), max(0, all_y1), min(w, all_x2), min(h, all_y2)]
    else:
        # Construct human bounding box directly from face
        box = [
            max(0, fx - int(fw * 0.35)),
            max(0, fy - int(fh * 0.15)),
            min(w, fx + fw + int(fw * 0.35)),
            min(h, fy + int(fh * 2.8))
        ]
        
    pad = int(max(fw, fh) * 0.15)
    face_crop = frame_bgr[max(0, fy-pad):min(h, fy+fh+pad), max(0, fx-pad):min(w, fx+fw+pad)]
    targets.append({'bbox': box, 'face_crop': face_crop, 'confidence': 0.95})
    used_faces.add(f_idx)

# Add remaining raw person boxes that had no face (e.g. distant people facing away)
for b_idx, (bx1, by1, bx2, by2) in enumerate(raw_boxes):
    is_part_of_face = False
    for t in targets:
        tb = t['bbox']
        inter = max(0, min(bx2, tb[2]) - max(bx1, tb[0])) * max(0, min(by2, tb[3]) - max(by1, tb[1]))
        a_b = (bx2 - bx1) * (by2 - by1)
        if a_b > 0 and inter / a_b > 0.5:
            is_part_of_face = True
            break
    if not is_part_of_face:
        targets.append({'bbox': [bx1, by1, bx2, by2], 'face_crop': None, 'confidence': 0.85})

print(f'Harmonized Targets: {len(targets)}')
for i, t in enumerate(targets):
    has_f = t['face_crop'] is not None
    print(f"  Target {i+1}: Box={t['bbox']}, HasFace={has_f}")

# Now test face matching on Target 1
emb1 = identifier.get_embedding(p1)
norm1 = emb1 / np.linalg.norm(emb1)

t1_face = targets[0]['face_crop']
emb_t1 = identifier.get_embedding(t1_face)
norm_t1 = emb_t1 / np.linalg.norm(emb_t1)

sim = float(np.dot(norm1, norm_t1))
print(f"Target 1 vs Registered Priya: similarity = {sim:.4f}")

# Compare against Sharma
s_face = cv2.imread('dataset/faces/ranger_sharma/face_01.jpg')
emb_s = identifier.get_embedding(s_face)
norm_s = emb_s / np.linalg.norm(emb_s)
sim_s = float(np.dot(norm_s, norm_t1))
print(f"Target 1 vs Registered Sharma: similarity = {sim_s:.4f}")

