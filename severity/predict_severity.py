import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ultralytics import YOLO
from severity.feature_extraction import extract_features
import joblib
import pandas as pd

# Load trained models
kmeans = joblib.load(PROJECT_ROOT / "severity" / "kmeans_model.pkl")
scaler = joblib.load(PROJECT_ROOT / "severity" / "scaler.pkl")

model = YOLO(str(PROJECT_ROOT / "models" / "best.pt"))

severity_map = {
    0: "Mild",
    1: "Moderate",
    2: "Severe"
}

def predict_image(image_path):
    results = model(image_path, conf=0.25)
    result = results[0]

    if result.masks is None:
        print("No defects found")
        return

    masks = result.masks.data.cpu().numpy()
    boxes = result.boxes

    for i, mask in enumerate(masks):
        cls = int(boxes.cls[i])
        label = result.names[cls]

        if label == "Wheel":
            continue

        features = extract_features(mask)

        vector = pd.DataFrame([{
            "area": features["area"],
            "perimeter": features["perimeter"],
            "aspect_ratio": features["aspect_ratio"],
            "edge_density": features["edge_density"],
            "entropy": features["entropy"]
        }])

        vector_scaled = scaler.transform(vector)
        cluster = kmeans.predict(vector_scaled)[0]

        severity = severity_map.get(cluster, "Unknown")

        print(f"{label}: {severity}")

if __name__ == "__main__":
    image_path = PROJECT_ROOT / "dataset" / "test" / "images" / "frame2304_jpg.rf.0188ac25e86fafbbdc3ca9a47b63a8e5.jpg"
    predict_image(str(image_path))