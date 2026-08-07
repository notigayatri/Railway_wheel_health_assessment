import cv2
import numpy as np
from ultralytics import YOLO
from pathlib import Path

from reliability.augmentations import generate_augmentations

# Load trained YOLO model
MODEL_PATH = Path("models/best.pt")
model = YOLO(MODEL_PATH)


DEFECT_CLASSES = {
    "Shelling",
    "Cracks-Scratches",
    "Discoloration"
}

def get_defect_confidences(result):
    """
    Return confidences for ALL detected defect classes
    (ignore the Wheel class).
    """

    defect_confidences = {}

    for box in result.boxes:
        class_id = int(box.cls[0])
        class_name = model.names[class_id]
        confidence = float(box.conf[0])

        # Ignore wheel class
        if class_name != "Wheel":
            # Keep highest confidence for that defect
            if class_name not in defect_confidences:
                defect_confidences[class_name] = confidence
            else:
                defect_confidences[class_name] = max(
                    defect_confidences[class_name],
                    confidence
                )

    return defect_confidences


def calculate_reliability(image_path):
    img = cv2.imread(str(image_path))

    if img is None:
        raise ValueError(f"Cannot read image: {image_path}")

    # Store confidences for each defect separately
    defect_history = {}

    for aug_name, aug_img in generate_augmentations(img):
        result = model(aug_img, verbose=False)[0]

        detections = get_defect_confidences(result)

        for defect, conf in detections.items():
            if defect not in defect_history:
                defect_history[defect] = []

            defect_history[defect].append(conf)

    final_results = {}

    for defect, confs in defect_history.items():
        mean_conf = float(np.mean(confs))
        std_conf = float(np.std(confs))

        if std_conf < 0.03:
            reliability = "HIGH"
        elif std_conf < 0.08:
            reliability = "MEDIUM"
        else:
            reliability = "LOW"

        final_results[defect] = {
            "mean_confidence": round(mean_conf, 3),
            "std_deviation": round(std_conf, 3),
            "reliability": reliability,
            "all_confidences": [round(c, 3) for c in confs]
        }

    return final_results