import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ultralytics import YOLO
import cv2


def run_detection(image_path, model_path=None):
    if model_path is None:
        model_path = PROJECT_ROOT / "models" / "best.pt"
    model = YOLO(str(model_path))

    results = model(image_path, conf=0.25)

    result = results[0]

    # Save annotated image
    annotated = result.plot()

    output_path = PROJECT_ROOT / "outputs" / "annotated" / Path(image_path).name
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cv2.imwrite(str(output_path), annotated)

    return result, output_path

if __name__ == "__main__":
    result, path = run_detection("images/test.jpg")
    print(f"Saved annotated image: {path}")