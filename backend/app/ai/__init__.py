"""
Backend AI service wrappers ? load project-trained models at startup.
Both detectors are initialized once and reused across requests.
"""
import os
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

_person_detector = None
_face_identifier = None


def get_person_detector(model_path: str = None, conf_threshold: float = 0.40):
    global _person_detector
    if _person_detector is None:
        from ai.person_detection.inference import ForestPersonDetector
        path = model_path or os.path.join(project_root, "models", "person_detector.pth")
        _person_detector = ForestPersonDetector(model_path=path, conf_threshold=conf_threshold)
    return _person_detector


def get_face_identifier(model_path: str = None, class_map_path: str = None, similarity_threshold: float = 0.65):
    global _face_identifier
    if _face_identifier is None:
        from ai.face_identification.inference import ForestFaceIdentifier
        m_path = model_path or os.path.join(project_root, "models", "face_identifier.pth")
        c_path = class_map_path or os.path.join(project_root, "models", "face_class_map.json")
        _face_identifier = ForestFaceIdentifier(
            model_path=m_path,
            class_map_path=c_path,
            similarity_threshold=similarity_threshold
        )
    return _face_identifier
