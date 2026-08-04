import cv2
import numpy as np
from skimage.measure import shannon_entropy

def extract_features(mask):
    mask = (mask * 255).astype(np.uint8)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return None

    c = max(contours, key=cv2.contourArea)

    area = cv2.contourArea(c)
    perimeter = cv2.arcLength(c, True)

    x, y, w, h = cv2.boundingRect(c)
    aspect_ratio = round(w / h, 3)

    edges = cv2.Canny(mask, 50, 150)
    edge_density = round(np.sum(edges > 0) / max(area, 1), 4)

    entropy = round(shannon_entropy(mask), 3)

    return {
        "area": round(area, 2),
        "perimeter": round(perimeter, 2),
        "aspect_ratio": aspect_ratio,
        "edge_density": edge_density,
        "entropy": entropy
    }