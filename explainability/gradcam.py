"""
Grad-CAM explainability for the wheel-defect YOLOv8 model.

Given an input image, this produces a heatmap overlay showing which
image regions most influenced the model's detections -- i.e. WHY the
model flagged a region as Shelling / Cracks-Scratches / Discoloration.

Usage:
    python explainability/gradcam.py path/to/image.jpg
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import cv2
import numpy as np
import torch
from ultralytics import YOLO
from pytorch_grad_cam import EigenCAM
from pytorch_grad_cam.utils.image import show_cam_on_image

MODEL_PATH = PROJECT_ROOT / "models" / "best.pt"
IMG_SIZE = 640

# Which internal YOLOv8 layer to read activations from.
# Layer 18 is the C2f block in the neck (P4 / mid-resolution feature map).
# This was chosen empirically for this model: layers close to the output
# (-2, -1) produced heatmaps dominated by image-border artifacts, while
# layer 18 produced heatmaps that actually concentrate on the wheel and
# defect regions. If you swap in a different best.pt (different YOLOv8
# variant/depth), re-check this by trying nearby indices (15, 18, 21) --
# see the layer-comparison note in the README.
TARGET_LAYER_INDEX = 18


class YOLOForwardWrapper(torch.nn.Module):
    """
    pytorch-grad-cam expects a plain nn.Module that returns a tensor
    from forward(). Ultralytics' YOLO wrapper does pre/post-processing
    (NMS, box decoding, etc.) that breaks gradient/activation hooks, so
    we call the underlying raw torch model (model.model) directly.
    """

    def __init__(self, yolo_model):
        super().__init__()
        self.model = yolo_model.model
        self.model.eval()

    def forward(self, x):
        # model(x) -> (predictions, protos) for a segmentation head, where
        # predictions[0] is the raw (batch, 4+num_classes+num_masks, num_anchors)
        # tensor. We only need that tensor for EigenCAM's activation hooks.
        raw = self.model(x)
        return raw[0][0] if isinstance(raw[0], (tuple, list)) else raw[0]


def reshape_transform(tensor):
    """
    EigenCAM needs a (batch, channels, height, width) activation map.
    For YOLOv8 detection/segmentation heads the raw feature map from the
    target layer is already in that shape, so this is a passthrough --
    kept as a hook point in case a different target layer is used later.
    """
    return tensor


def load_image(image_path):
    bgr = cv2.imread(str(image_path))
    if bgr is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")
    bgr = cv2.resize(bgr, (IMG_SIZE, IMG_SIZE))
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    rgb_float = np.float32(rgb) / 255.0
    tensor = torch.from_numpy(rgb_float).permute(2, 0, 1).unsqueeze(0)
    return rgb_float, tensor


def draw_boxes(cam_image_rgb, result, img_size):
    """Draw the model's own detection boxes + labels on top of the heatmap,
    so it's clear which defect each hot region belongs to."""
    if result.boxes is None:
        return cam_image_rgb

    h0, w0 = result.orig_shape
    sx, sy = img_size / w0, img_size / h0

    out = cam_image_rgb.copy()
    for box in result.boxes:
        cls = int(box.cls[0])
        label = result.names[cls]
        conf = float(box.conf[0])
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        x1, x2 = int(x1 * sx), int(x2 * sx)
        y1, y2 = int(y1 * sy), int(y2 * sy)
        cv2.rectangle(out, (x1, y1), (x2, y2), (255, 255, 255), 2)
        cv2.putText(out, f"{label} {conf:.2f}", (x1, max(y1 - 6, 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    return out


def generate_gradcam(image_path, output_path=None, model_path=MODEL_PATH):
    yolo = YOLO(str(model_path))
    wrapped_model = YOLOForwardWrapper(yolo)

    target_layers = [wrapped_model.model.model[TARGET_LAYER_INDEX]]

    rgb_float, input_tensor = load_image(image_path)

    with EigenCAM(model=wrapped_model, target_layers=target_layers,
                  reshape_transform=reshape_transform) as cam:
        grayscale_cam = cam(input_tensor)[0, :, :]

    cam_image = show_cam_on_image(rgb_float, grayscale_cam, use_rgb=True)

    # Run a normal prediction pass to get boxes for the overlay.
    result = yolo(str(image_path), conf=0.25)[0]
    cam_image = draw_boxes(cam_image, result, IMG_SIZE)

    cam_image_bgr = cv2.cvtColor(cam_image, cv2.COLOR_RGB2BGR)

    if output_path is None:
        output_path = PROJECT_ROOT / "outputs" / "gradcam" / Path(image_path).name
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cv2.imwrite(str(output_path), cam_image_bgr)
    return output_path


if __name__ == "__main__":
    if len(sys.argv) > 1:
        img_path = sys.argv[1]
    else:
        img_path = PROJECT_ROOT / "images" / "test_image_4.jpg"

    out = generate_gradcam(img_path)
    print(f"Saved Grad-CAM heatmap: {out}")
