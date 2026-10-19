import os
import unittest
import numpy as np
import torch
from ai.person_detection.model import ForestPersonNet
from ai.person_detection.inference import ForestPersonDetector, compute_iou
from ai.face_identification.model import ForestFaceNet
from ai.face_identification.inference import ForestFaceIdentifier

class TestAIModels(unittest.TestCase):
    """Unit tests for Custom AI models trained from scratch without pretrained weights."""

    def test_person_net_forward_pass(self):
        """Test ForestPersonNet architecture forward pass and tensor dimensions."""
        model = ForestPersonNet(grid_size=7, num_classes=1)
        model.eval()
        dummy_input = torch.randn(2, 3, 224, 224)
        with torch.no_grad():
            output = model(dummy_input)
        
        # Expected shape: [batch, grid_size, grid_size, 6] (tx, ty, tw, th, p_obj, p_cls)
        self.assertEqual(output.shape, (2, 7, 7, 6))

    def test_face_net_forward_pass_and_norm(self):
        """Test ForestFaceNet embedding extraction and L2 normalization."""
        model = ForestFaceNet(embedding_dim=128, num_classes=5)
        model.eval()
        dummy_input = torch.randn(2, 3, 112, 112)
        with torch.no_grad():
            embeddings, logits = model(dummy_input)
        
        self.assertEqual(embeddings.shape, (2, 128))
        self.assertEqual(logits.shape, (2, 5))
        
        # L2-norm of each embedding vector must be ~1.0
        norms = torch.norm(embeddings, p=2, dim=1).numpy()
        np.testing.assert_allclose(norms, [1.0, 1.0], atol=1e-5)

    def test_compute_iou(self):
        """Test bounding box Intersection over Union (IoU) calculation."""
        # Exact match
        box_a = [10, 10, 50, 50]
        box_b = [10, 10, 50, 50]
        self.assertAlmostEqual(compute_iou(box_a, box_b), 1.0, places=4)

        # Disjoint boxes
        box_c = [100, 100, 150, 150]
        self.assertEqual(compute_iou(box_a, box_c), 0.0)

        # 50% overlap scenario
        # Box 1: [0, 0, 10, 10] -> Area 100
        # Box 2: [0, 0, 5, 10]  -> Area 50
        # Intersection: 50, Union: 100 -> IoU = 0.5
        box_d = [0, 0, 10, 10]
        box_e = [0, 0, 5, 10]
        self.assertAlmostEqual(compute_iou(box_d, box_e), 0.5, places=4)

    def test_trained_person_detector_inference(self):
        """Test loading trained ForestPersonDetector and running inference on an image."""
        model_path = "models/person_detector.pth"
        if not os.path.exists(model_path):
            self.skipTest(f"Model checkpoint {model_path} not found.")

        detector = ForestPersonDetector(model_path=model_path, conf_threshold=0.3)
        self.assertTrue(detector.is_trained)

        # Create dummy synthetic image (H, W, 3) in uint8 BGR
        synthetic_img = np.zeros((480, 640, 3), dtype=np.uint8)
        # Draw a bright rectangle to simulate contrast
        synthetic_img[100:300, 200:400] = [180, 180, 180]

        result = detector.detect(synthetic_img)
        self.assertIsInstance(result, dict)
        self.assertIn("person_count", result)
        self.assertIn("detections", result)
        self.assertIsInstance(result["detections"], list)

    def test_trained_face_identifier_embedding(self):
        """Test loading trained ForestFaceIdentifier and extracting 128-D embedding."""
        model_path = "models/face_identifier.pth"
        class_map_path = "models/face_class_map.json"
        if not os.path.exists(model_path):
            self.skipTest(f"Model checkpoint {model_path} not found.")

        identifier = ForestFaceIdentifier(model_path=model_path, class_map_path=class_map_path)
        self.assertTrue(identifier.is_trained)

        # Dummy face image 112x112 BGR
        dummy_face = np.random.randint(50, 200, (112, 112, 3), dtype=np.uint8)
        embedding = identifier.get_embedding(dummy_face)
        
        self.assertIsNotNone(embedding)
        self.assertEqual(len(embedding), 128)
        norm = np.linalg.norm(embedding)
        self.assertAlmostEqual(float(norm), 1.0, places=4)

if __name__ == "__main__":
    unittest.main()
