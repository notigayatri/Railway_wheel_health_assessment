import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ultralytics import YOLO
from severity.feature_extraction import extract_features
import pandas as pd

model = YOLO(str(PROJECT_ROOT / "models" / "best.pt"))

candidate_dirs = [
    PROJECT_ROOT / "dataset" / "train" / "images",
]

train_dir = None
for candidate in candidate_dirs:
    if candidate.exists() and any(candidate.glob("*.jpg")):
        train_dir = candidate
        break

if train_dir is None:
    raise FileNotFoundError("No training images found. Expected images under dataset/train/images or dataset/images")

records = []

for image_path in sorted(train_dir.glob("*.jpg")):
    results = model(str(image_path), conf=0.25)
    result = results[0]

    if result.masks is None:
        continue

    masks = result.masks.data.cpu().numpy()
    boxes = result.boxes

    for i, mask in enumerate(masks):
        cls = int(boxes.cls[i])
        label = result.names[cls]

        if label == "Wheel":
            continue

        features = extract_features(mask)

        if features:
            features["class"] = label
            records.append(features)

df = pd.DataFrame(records)
output_csv = PROJECT_ROOT / "outputs" / "training_features.csv"
output_csv.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(output_csv, index=False)

print(f"Processed {len(list(train_dir.glob('*.jpg')))} images from {train_dir}")
print(f"Extracted {len(df)} defect samples")