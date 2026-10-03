import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ultralytics import YOLO
from severity.feature_extraction import extract_features
import json
import joblib
import pandas as pd

# Load trained models
kmeans = joblib.load(PROJECT_ROOT / "severity" / "kmeans_model.pkl")
scaler = joblib.load(PROJECT_ROOT / "severity" / "scaler.pkl")

# Load YOLO model
model = YOLO(str(PROJECT_ROOT / "models" / "best.pt"))

# Documented Cluster-to-Severity Mapping established from training feature distributions:
# Cluster 1: Area mean ~578 px, perimeter mean ~121 px -> Mild
# Cluster 2: Area mean ~763 px, perimeter mean ~216 px, aspect ratio ~7.61 (cracks) -> Moderate
# Cluster 0: Area mean ~2983 px, perimeter mean ~315 px, entropy ~0.064 -> Severe
DEFAULT_SEVERITY_MAP = {
    0: "Severe",
    1: "Mild",
    2: "Moderate"
}

mapping_file = PROJECT_ROOT / "severity" / "severity_mapping.json"
if mapping_file.exists():
    try:
        with open(mapping_file, "r") as f:
            raw_map = json.load(f)
            severity_map = {int(k): v for k, v in raw_map.items()}
    except Exception:
        severity_map = DEFAULT_SEVERITY_MAP
else:
    severity_map = DEFAULT_SEVERITY_MAP


def predict_image(image_path):
    """
    Detect defects, extract features, predict severity using the
    already trained K-Means model, and return results as a dictionary.
    """

    results = model(str(image_path), conf=0.25)
    result = results[0]

    if result.masks is None:
        print("No defects found")
        return {}

    masks = result.masks.data.cpu().numpy()
    boxes = result.boxes

    severity_results = {}

    print("===== SEVERITY ANALYSIS =====")

    for i, mask in enumerate(masks):
        cls = int(boxes.cls[i])
        label = result.names[cls]

        # Skip wheel class
        if label == "Wheel":
            continue

        # Extract numerical features
        features = extract_features(mask)

        if features is None:
            continue

        # Create feature vector
        vector = pd.DataFrame([
            {
                "area": features["area"],
                "perimeter": features["perimeter"],
                "aspect_ratio": features["aspect_ratio"],
                "edge_density": features["edge_density"],
                "entropy": features["entropy"]
            }
        ])

        # Scale features using trained scaler
        vector_scaled = scaler.transform(vector)

        # Predict cluster using trained K-Means model
        cluster = kmeans.predict(vector_scaled)[0]

        severity = severity_map.get(cluster, "Unknown")

        severity_results[label] = severity

        print(f"{label}: {severity}")

    return severity_results


if __name__ == "__main__":
    image_path = (
        PROJECT_ROOT
        / "dataset"
        / "test"
        / "images"
        / "frame2304_jpg.rf.0188ac25e86fafbbdc3ca9a47b63a8e5.jpg"
    )

    results = predict_image(image_path)

    print("\\nReturned Dictionary:")
    print(results)


def predict_image_detailed(image_path):
    """
    Extended version of predict_image() for the FastAPI backend.

    Returns a tuple:
        (detections, yolo_result)

    Where detections is a list of dicts, one per individual defect
    detection (duplicates of the same class are preserved as separate
    entries, indexed by their mask index):

        {
            "index":        int,           # position in the mask array
            "label":        str,           # e.g. "Shelling"
            "confidence":   float,
            "severity":     str,           # Mild / Moderate / Severe
            "features": {
                "area":         float,
                "perimeter":    float,
                "aspect_ratio": float,
                "edge_density": float,
                "entropy":      float,
            }
        }

    yolo_result is the raw ultralytics Result object (needed by
    detect_and_annotate() in the API layer).
    """
    results = model(str(image_path), conf=0.25)
    yolo_result = results[0]

    detections = []

    if yolo_result.masks is None:
        return detections, yolo_result

    masks = yolo_result.masks.data.cpu().numpy()
    boxes = yolo_result.boxes

    for i, mask in enumerate(masks):
        cls = int(boxes.cls[i])
        label = yolo_result.names[cls]

        if label == "Wheel":
            continue

        conf = round(float(boxes.conf[i]), 3)
        features = extract_features(mask)

        if features is None:
            continue

        vector = pd.DataFrame([
            {
                "area":         features["area"],
                "perimeter":    features["perimeter"],
                "aspect_ratio": features["aspect_ratio"],
                "edge_density": features["edge_density"],
                "entropy":      features["entropy"],
            }
        ])

        vector_scaled = scaler.transform(vector)
        cluster = kmeans.predict(vector_scaled)[0]
        severity = severity_map.get(cluster, "Unknown")

        detections.append({
            "index":      i,
            "label":      label,
            "confidence": conf,
            "severity":   severity,
            "features":   features,
        })

    return detections, yolo_result