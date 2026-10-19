import os
import cv2
import numpy as np
import base64
import unittest
from backend.app import create_app
from backend.app.services.visitor_service import (
    process_detection_frame,
    register_face_biometric,
    register_face_biometrics_multi,
    delete_registered_visitor,
    toggle_visitor_status,
    reload_embeddings_cache,
    db_conn,
    REGISTERED_EMBEDDINGS_CACHE,
    MARGIN_THRESHOLD
)


class TestGroupFaceIdentification(unittest.TestCase):
    """Verifies that in a group of people, only the registered person is identified,
    and different unregistered persons are never assigned the same name."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app_context = cls.app.app_context()
        cls.app_context.push()

        # Enroll Ranger Priya into database
        priya_img = cv2.imread("dataset/faces/ranger_priya/face_01.jpg")
        assert priya_img is not None, "Failed to load test face"
        _, enc = cv2.imencode(".jpg", priya_img)
        b64 = "data:image/jpeg;base64," + base64.b64encode(enc).decode("utf-8")

        emb_bytes, thumb, err = register_face_biometric(b64)
        assert err is None, f"Biometric registration error: {err}"
        cls.priya_emb_bytes = emb_bytes

        # Back up existing database state to isolate test environment
        with db_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT unique_id, name, phone, email, registered_at, status, face_registered, samples_count FROM registrations")
            cls._backup_registrations = cur.fetchall()
            cur.execute("SELECT unique_id, name, embedding, face_thumbnail, samples_count, created_at FROM visitor_face_embeddings")
            cls._backup_embeddings = cur.fetchall()
            cur.execute("SELECT unique_id, sample_index, image_path, embedding, created_at FROM visitor_face_samples")
            cls._backup_samples = cur.fetchall()

            conn.execute("DELETE FROM visitor_face_samples")
            conn.execute("DELETE FROM visitor_face_embeddings")
            conn.execute("DELETE FROM registrations")

            # Enroll Ranger Priya into database
            conn.execute("""
                INSERT INTO registrations (unique_id, name, phone, email, registered_at, status, face_registered, samples_count)
                VALUES ('FOR-TEST-PRIYA', 'Ranger Priya', '9876543211', 'priya@forest.gov', '2026-09-17 00:00:00', 'Active', 1, 1)
            """)
            conn.execute(
                """INSERT INTO visitor_face_embeddings 
                   (unique_id, name, embedding, face_thumbnail, samples_count, created_at) 
                   VALUES (?, ?, ?, ?, 1, ?)""",
                ("FOR-TEST-PRIYA", "Ranger Priya", emb_bytes, thumb, "2026-09-17 00:00:00")
            )
        reload_embeddings_cache()

    @classmethod
    def tearDownClass(cls):
        with db_conn() as conn:
            conn.execute("DELETE FROM visitor_face_samples")
            conn.execute("DELETE FROM visitor_face_embeddings")
            conn.execute("DELETE FROM registrations")

            # Restore original rows
            if hasattr(cls, '_backup_registrations'):
                conn.executemany(
                    "INSERT INTO registrations (unique_id, name, phone, email, registered_at, status, face_registered, samples_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    cls._backup_registrations
                )
            if hasattr(cls, '_backup_embeddings'):
                conn.executemany(
                    "INSERT INTO visitor_face_embeddings (unique_id, name, embedding, face_thumbnail, samples_count, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    cls._backup_embeddings
                )
            if hasattr(cls, '_backup_samples'):
                conn.executemany(
                    "INSERT INTO visitor_face_samples (unique_id, sample_index, image_path, embedding, created_at) VALUES (?, ?, ?, ?, ?)",
                    cls._backup_samples
                )
        reload_embeddings_cache()
        cls.app_context.pop()

    def test_01_single_person_registered_identification(self):
        """A registered person (Ranger Priya) alone in a frame must be identified with high confidence."""
        p2 = cv2.imread("dataset/faces/ranger_priya/face_02.jpg")
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[100:240, 200:310] = cv2.resize(p2, (110, 140))

        res = process_detection_frame(frame)
        people = res["people"]
        self.assertGreater(len(people), 0, "Target face should be detected")
        
        priya = people[0]
        self.assertEqual(priya["status"], "REGISTERED")
        self.assertEqual(priya["visitor_name"], "Ranger Priya")
        self.assertEqual(priya["visitor_id"], "FOR-TEST-PRIYA")
        self.assertGreaterEqual(priya["match_confidence"], 0.50)

    def test_02_single_person_unregistered(self):
        """An unregistered person (Ranger Sharma) alone in a frame must be strictly UNREGISTERED."""
        s1 = cv2.imread("dataset/faces/ranger_sharma/face_01.jpg")
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[100:240, 200:310] = cv2.resize(s1, (110, 140))

        res = process_detection_frame(frame)
        people = res["people"]
        self.assertGreater(len(people), 0, "Target face should be detected")

        target = people[0]
        self.assertEqual(target["status"], "UNREGISTERED")
        self.assertEqual(target["visitor_name"], "UNREGISTERED")
        self.assertEqual(target["visitor_id"], "UNREGISTERED")

    def test_03_group_identification_uniqueness(self):
        """In a group with Priya (registered), Sharma (unregistered), and Deepa (unregistered),
        only Priya is identified, non-Priya faces are UNREGISTERED, and Priya is assigned at most once."""
        p2 = cv2.imread("dataset/faces/ranger_priya/face_02.jpg")
        s1 = cv2.imread("dataset/faces/ranger_sharma/face_01.jpg")
        d1 = cv2.imread("dataset/faces/visitor_deepa/face_01.jpg")

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[100:240, 50:160]  = cv2.resize(p2, (110, 140))
        frame[100:240, 260:370] = cv2.resize(s1, (110, 140))
        frame[100:240, 470:580] = cv2.resize(d1, (110, 140))

        res = process_detection_frame(frame)
        people = res["people"]
        self.assertGreater(len(people), 0, "Expected at least 1 person detected")

        priya_matches = [p for p in people if p["visitor_name"] == "Ranger Priya"]
        self.assertLessEqual(len(priya_matches), 1, "Duplicate assignment detected! Ranger Priya assigned to multiple targets.")

        for p in people:
            if p["status"] == "REGISTERED":
                self.assertEqual(p["visitor_name"], "Ranger Priya")
                self.assertEqual(p["visitor_id"], "FOR-TEST-PRIYA")
                self.assertGreaterEqual(p["match_confidence"], 0.50)
            else:
                self.assertEqual(p["status"], "UNREGISTERED")
                self.assertEqual(p["visitor_name"], "UNREGISTERED")
                self.assertEqual(p["visitor_id"], "UNREGISTERED")

    def test_04_group_with_no_registered_person(self):
        """In a group with only unregistered people (Sharma + Deepa), neither must be labeled Priya."""
        s1 = cv2.imread("dataset/faces/ranger_sharma/face_01.jpg")
        d1 = cv2.imread("dataset/faces/visitor_deepa/face_01.jpg")

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[100:240, 100:210] = cv2.resize(s1, (110, 140))
        frame[100:240, 350:460] = cv2.resize(d1, (110, 140))

        res = process_detection_frame(frame)
        people = res["people"]

        for p in people:
            self.assertEqual(p["status"], "UNREGISTERED")
            self.assertEqual(p["visitor_name"], "UNREGISTERED")
            self.assertEqual(p["visitor_id"], "UNREGISTERED")

    def test_05_frame_one_to_one_locking(self):
        """Duplicate identical faces of Priya in the same frame must match AT MOST ONE target.
        The second face must be strictly UNREGISTERED to prevent identity duplication."""
        p2 = cv2.imread("dataset/faces/ranger_priya/face_02.jpg")

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[100:240, 100:210] = cv2.resize(p2, (110, 140))
        frame[100:240, 350:460] = cv2.resize(p2, (110, 140))

        res = process_detection_frame(frame)
        people = res["people"]
        self.assertGreaterEqual(len(people), 2, "Expected both faces detected")

        priya_matches = [p for p in people if p["visitor_id"] == "FOR-TEST-PRIYA"]
        self.assertEqual(len(priya_matches), 1, "1-to-1 locking failed: FOR-TEST-PRIYA assigned multiple times in frame")

        unregistered = [p for p in people if p["visitor_id"] == "UNREGISTERED"]
        self.assertEqual(len(unregistered), len(people) - 1)

    def test_06_ambiguous_margin_rejection(self):
        """When two registered profiles produce similarity values within the margin threshold (< 0.08),
        the system must reject the match and output UNREGISTERED to prevent false identification."""
        priya_emb = np.frombuffer(self.priya_emb_bytes, dtype=np.float32)

        # Create a synthetic near-clone vector with similarity margin < 0.08
        clone_emb = priya_emb + np.random.normal(0, 0.01, size=priya_emb.shape).astype(np.float32)
        clone_emb = clone_emb / np.linalg.norm(clone_emb)
        clone_bytes = clone_emb.astype(np.float32).tobytes()

        with db_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO visitor_face_embeddings
                (unique_id, name, embedding, face_thumbnail, samples_count, created_at)
                VALUES ('FOR-TEST-CLONE', 'Clone Persona', ?, '', 1, '2026-09-17 00:00:00')
            """, (clone_bytes,))
            conn.execute("""
                INSERT OR REPLACE INTO registrations
                (unique_id, name, phone, email, registered_at, status)
                VALUES ('FOR-TEST-CLONE', 'Clone Persona', '0000000000', 'clone@test.com', '2026-09-17 00:00:00', 'Active')
            """)
        reload_embeddings_cache()

        try:
            p2 = cv2.imread("dataset/faces/ranger_priya/face_02.jpg")
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            frame[100:240, 200:310] = cv2.resize(p2, (110, 140))

            res = process_detection_frame(frame)
            people = res["people"]
            self.assertGreater(len(people), 0)

            # Because margin < MARGIN_THRESHOLD (0.08), it must be rejected as UNREGISTERED
            target = people[0]
            self.assertEqual(target["status"], "UNREGISTERED", 
                             f"Ambiguous match was not rejected! Margin: {target.get('margin')}")
            self.assertEqual(target["visitor_name"], "UNREGISTERED")
        finally:
            with db_conn() as conn:
                conn.execute("DELETE FROM registrations WHERE unique_id = 'FOR-TEST-CLONE'")
                conn.execute("DELETE FROM visitor_face_embeddings WHERE unique_id = 'FOR-TEST-CLONE'")
            reload_embeddings_cache()

    def test_07_multi_photo_enrollment(self):
        """Verify register_face_biometrics_multi captures 3 real photos, computes normalized centroid,
        stores samples on disk and in visitor_face_samples table."""
        p1 = cv2.imread("dataset/faces/ranger_priya/face_01.jpg")
        p2 = cv2.imread("dataset/faces/ranger_priya/face_02.jpg")
        p3 = cv2.imread("dataset/faces/ranger_priya/face_03.jpg")

        b64_list = []
        for img in [p1, p2, p3]:
            _, enc = cv2.imencode(".jpg", img)
            b64_list.append("data:image/jpeg;base64," + base64.b64encode(enc).decode("utf-8"))

        with db_conn() as conn:
            conn.execute("DELETE FROM registrations WHERE unique_id = 'FOR-TEST-MULTI'")
            conn.execute("DELETE FROM visitor_face_embeddings WHERE unique_id = 'FOR-TEST-MULTI'")
            conn.execute("DELETE FROM visitor_face_samples WHERE unique_id = 'FOR-TEST-MULTI'")
            conn.execute("""
                INSERT INTO registrations (unique_id, name, phone, email, registered_at, status)
                VALUES ('FOR-TEST-MULTI', 'Multi Test Person', '9876543212', 'multi@test.com', '2026-09-17 00:00:00', 'Active')
            """)

        centroid_bytes, thumb_b64, count, err = register_face_biometrics_multi(
            b64_list, "FOR-TEST-MULTI", "Multi Test Person"
        )

        self.assertIsNone(err)
        self.assertIsNotNone(centroid_bytes)
        self.assertEqual(count, 3)
        self.assertTrue(thumb_b64.startswith("data:image/jpeg;base64,"))

        # Check disk files
        for i in range(1, 4):
            disk_path = f"dataset/faces/FOR-TEST-MULTI/face_{i:02d}.jpg"
            self.assertTrue(os.path.exists(disk_path), f"Disk file missing: {disk_path}")

        # Check database records
        with db_conn(True) as conn:
            # Check samples
            samples = conn.execute("SELECT * FROM visitor_face_samples WHERE unique_id = 'FOR-TEST-MULTI'").fetchall()
            self.assertEqual(len(samples), 3)

            # Check embeddings row
            emb_row = conn.execute("SELECT * FROM visitor_face_embeddings WHERE unique_id = 'FOR-TEST-MULTI'").fetchone()
            self.assertIsNotNone(emb_row)
            self.assertEqual(emb_row["samples_count"], 3)

            # Centroid vector must be L2-normalized
            c_vec = np.frombuffer(emb_row["embedding"], dtype=np.float32)
            self.assertAlmostEqual(np.linalg.norm(c_vec), 1.0, places=4)

    def test_08_toggle_visitor_status(self):
        """Toggling a registered visitor to Disabled must immediately exclude them from
        the recognition cache so they are reported as UNREGISTERED in live frames."""
        # 1. Disable FOR-TEST-MULTI
        res_toggle = toggle_visitor_status("FOR-TEST-MULTI")
        self.assertTrue(res_toggle["success"])
        self.assertEqual(res_toggle["new_status"], "Disabled")

        # Check cache exclusion
        global REGISTERED_EMBEDDINGS_CACHE
        uids_in_cache = [p["unique_id"] for p in REGISTERED_EMBEDDINGS_CACHE]
        self.assertNotIn("FOR-TEST-MULTI", uids_in_cache, "Disabled visitor should NOT be present in recognition cache")

        # 2. Re-enable FOR-TEST-MULTI
        res_enable = toggle_visitor_status("FOR-TEST-MULTI")
        self.assertTrue(res_enable["success"])
        self.assertEqual(res_enable["new_status"], "Active")

        from backend.app.services.visitor_service import REGISTERED_EMBEDDINGS_CACHE as updated_cache
        uids_in_cache2 = [p["unique_id"] for p in updated_cache]
        self.assertIn("FOR-TEST-MULTI", uids_in_cache2, "Active visitor should be present in recognition cache")

    def test_09_cascading_deletion(self):
        """Cascading deletion must purge registrations, embeddings, samples, and disk directory."""
        disk_dir = os.path.join("dataset", "faces", "FOR-TEST-MULTI")
        self.assertTrue(os.path.exists(disk_dir), "Enrollment directory should exist prior to deletion")

        res_del = delete_registered_visitor("FOR-TEST-MULTI")
        self.assertTrue(res_del["success"])

        # Disk directory must be removed
        self.assertFalse(os.path.exists(disk_dir), "Enrollment directory must be deleted from disk")

        # Database rows must be purged
        with db_conn(True) as conn:
            reg = conn.execute("SELECT * FROM registrations WHERE unique_id = 'FOR-TEST-MULTI'").fetchone()
            self.assertIsNone(reg)

            emb = conn.execute("SELECT * FROM visitor_face_embeddings WHERE unique_id = 'FOR-TEST-MULTI'").fetchone()
            self.assertIsNone(emb)

            samples = conn.execute("SELECT * FROM visitor_face_samples WHERE unique_id = 'FOR-TEST-MULTI'").fetchall()
            self.assertEqual(len(samples), 0)

        # In-memory cache must not contain the deleted visitor
        from backend.app.services.visitor_service import REGISTERED_EMBEDDINGS_CACHE as active_cache
        cached_uids = [p["unique_id"] for p in active_cache]
        self.assertNotIn("FOR-TEST-MULTI", cached_uids)


if __name__ == "__main__":
    unittest.main()
