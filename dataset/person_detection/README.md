# Smart Forest Person Detection - Real Photographic Dataset

## Dataset Provenance & Ethics
This dataset contains **100% authentic photographic imagery** of real human individuals and groups traversing outdoor forest vegetation and canopy zones.
- **Source**: Autonomous UAV Research Section, ETRI (ForestPersons Benchmark Dataset)
- **Official Repository**: [Hugging Face etri/ForestPersons](https://huggingface.co/datasets/etri/ForestPersons)
- **License**: Creative Commons Attribution-NonCommercial-ShareAlike 4.0 (CC BY-NC-SA 4.0)
- **Sensors**: GoPro / MAV Ultra-HD Optical Sensors
- **Environment**: Summer forest canopy, high tree density, variable illumination, shadow patterns, trail corridors.

## Structure
```
dataset/person_detection/
    images/
        train/   # Real training photographs
        val/     # Real validation photographs
        test/    # Real unseen testing photographs
    labels/
        train/   # Normalized YOLO annotations
        val/     # Normalized YOLO annotations
        test/    # Normalized YOLO annotations
    dataset_metadata.csv
    README.md
```

## Annotation Format (YOLO Normalized)
Each bounding box line contains:
`<class_id> <x_center> <y_center> <width> <height>`
Where:
- `class_id`: 0 (`person`)
- Coordinates are normalized to [0.0, 1.0].
