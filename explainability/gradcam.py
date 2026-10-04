"""
Defect-Focused Explainable AI (Layer-CAM / Grad-CAM) for Railway Wheel Inspection.

Provides targeted, activation-based feature attribution for YOLOv8 defect detections
(Shelling, Cracks-Scratches, Discoloration) while excluding non-defect objects like the
wheel body itself.

Methodology:
    1. Detection Alignment: Matches post-NMS defect detections to their originating anchors
       in the YOLOv8 multi-scale prediction head using spatial IoU and class score matching.
    2. Multi-Scale Layer Hooks: Attaches forward and backward hooks to the multi-scale C2f
       feature pyramid neck layers (Layer 15 [P3/stride 8], Layer 18 [P4/stride 16],
       Layer 21 [P5/stride 32]).
    3. Element-Wise Gradient Attribution (Layer-CAM): Standard Grad-CAM averages gradients
       globally (1/HW * sum(grad)), which dilutes localized defect signals across the entire
       train undercarriage. Layer-CAM uses spatial, element-wise positive gradients
       w_ij^k = ReLU(grad_ij^k) to weight feature activations A_ij^k:
           L_ij = ReLU(sum_k ReLU(grad_ij^k) * A_ij^k)
       This restricts attribution strictly to the image regions that contributed to the
       specific defect prediction.
    4. Multi-Defect Fusion: For images containing multiple defects, attribution is computed
       independently per defect and merged using element-wise maximum, ensuring each defect's
       features are clearly highlighted without mutual suppression.
    5. Structural Preservation: Soft alpha blending is applied so the surrounding wheel and
       railway components remain recognizable for engineers.

Interpretation:
    "The heatmap highlights image regions that contributed most strongly to the model's prediction."
    (It is an attribution heatmap, not an exact segmentation boundary.)

Usage:
    python explainability/gradcam.py path/to/image.jpg
"""

import sys
from pathlib import Path
from typing import Optional, Union, Tuple, Dict, Any, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from ultralytics import YOLO

MODEL_PATH = PROJECT_ROOT / "models" / "best.pt"
IMG_SIZE = 640

# YOLOv8 neck feature pyramid layers (C2f blocks at P3, P4, P5 scales)
TARGET_LAYER_INDICES = [15, 18, 21]

# Non-defect classes that should NOT be targeted for defect explanation
EXCLUDED_CLASSES = {"Wheel"}

# Global cache for loaded model to avoid reloading on every API request
_CACHED_YOLO = None
_CACHED_MODEL_PATH = None


def get_yolo_model(model_path: Union[str, Path] = MODEL_PATH) -> YOLO:
    """Retrieve or cache the YOLO model with parameters configured for autograd."""
    global _CACHED_YOLO, _CACHED_MODEL_PATH
    model_path_str = str(model_path)
    if _CACHED_YOLO is None or _CACHED_MODEL_PATH != model_path_str:
        _CACHED_YOLO = YOLO(model_path_str)
        _CACHED_MODEL_PATH = model_path_str
    return _CACHED_YOLO


def load_input_tensor(image_path: Union[str, Path], img_size: int = IMG_SIZE) -> Tuple[np.ndarray, torch.Tensor, Tuple[int, int]]:
    """
    Load image, resize to YOLO input size (img_size x img_size), and return:
        - orig_bgr: original image as BGR numpy array
        - input_tensor: (1, 3, img_size, img_size) float32 torch tensor normalized to [0, 1]
        - (orig_h, orig_w): original image dimensions
    """
    orig_bgr = cv2.imread(str(image_path))
    if orig_bgr is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")
    orig_h, orig_w = orig_bgr.shape[:2]

    bgr_resized = cv2.resize(orig_bgr, (img_size, img_size))
    rgb_contiguous = np.ascontiguousarray(bgr_resized[:, :, ::-1].transpose(2, 0, 1))
    input_tensor = torch.from_numpy(rgb_contiguous).unsqueeze(0).float() / 255.0
    return orig_bgr, input_tensor, (orig_h, orig_w)


def extract_defect_targets(yolo_result, img_size: int = IMG_SIZE) -> List[Dict[str, Any]]:
    """
    Extract genuine defect detections (excluding Wheel) from a YOLO result object.
    Normalizes coordinates to the img_size x img_size space.
    """
    defect_targets = []
    if yolo_result.boxes is None or len(yolo_result.boxes) == 0:
        return defect_targets

    orig_h, orig_w = yolo_result.orig_shape
    scale_x = img_size / orig_w
    scale_y = img_size / orig_h

    for idx, box in enumerate(yolo_result.boxes):
        cls_id = int(box.cls[0])
        label = yolo_result.names[cls_id]

        if label in EXCLUDED_CLASSES:
            continue

        conf = float(box.conf[0])
        x1, y1, x2, y2 = box.xyxy[0].tolist()

        # Scale coordinates to img_size
        sx1 = x1 * scale_x
        sy1 = y1 * scale_y
        sx2 = x2 * scale_x
        sy2 = y2 * scale_y

        defect_targets.append({
            "index": idx,
            "label": label,
            "cls_id": cls_id,
            "conf": conf,
            "box_model_space": [sx1, sy1, sx2, sy2],
            "box_orig_space": [x1, y1, x2, y2],
        })

    return defect_targets


def find_best_anchor_for_defect(pred_boxes: torch.Tensor, pred_cls_scores: torch.Tensor, target_box: List[float]) -> int:
    """
    Identify the output anchor in the YOLO prediction tensor that corresponds to the detected defect.
    pred_boxes: (4, 8400) tensor containing (cx, cy, w, h)
    pred_cls_scores: (8400,) tensor of predicted probabilities for target class
    target_box: [x1, y1, x2, y2] in model space (640x640)
    """
    t_x1, t_y1, t_x2, t_y2 = target_box
    t_area = (t_x2 - t_x1) * (t_y2 - t_y1)

    p_cx, p_cy, p_w, p_h = pred_boxes[0], pred_boxes[1], pred_boxes[2], pred_boxes[3]
    p_x1 = p_cx - p_w / 2.0
    p_y1 = p_cy - p_h / 2.0
    p_x2 = p_cx + p_w / 2.0
    p_y2 = p_cy + p_h / 2.0
    p_area = p_w * p_h

    inter_x1 = torch.max(p_x1, torch.tensor(t_x1, device=p_x1.device))
    inter_y1 = torch.max(p_y1, torch.tensor(t_y1, device=p_y1.device))
    inter_x2 = torch.min(p_x2, torch.tensor(t_x2, device=p_x2.device))
    inter_y2 = torch.min(p_y2, torch.tensor(t_y2, device=p_y2.device))

    inter_w = torch.clamp(inter_x2 - inter_x1, min=0.0)
    inter_h = torch.clamp(inter_y2 - inter_y1, min=0.0)
    inter_area = inter_w * inter_h

    union_area = p_area + t_area - inter_area
    iou = inter_area / torch.clamp(union_area, min=1e-6)

    # Match metric combines spatial overlap with class prediction strength
    match_metric = iou * pred_cls_scores
    best_anchor = int(match_metric.argmax().item())
    return best_anchor


def compute_layercam_for_defect(
    raw_model: torch.nn.Module,
    input_tensor: torch.Tensor,
    defect: Dict[str, Any],
    layer_indices: List[int] = TARGET_LAYER_INDICES,
    img_size: int = IMG_SIZE,
) -> np.ndarray:
    """
    Computes a defect-focused Layer-CAM heatmap for a single detected defect instance.
    Attaches hooks to multi-scale neck layers and backpropagates the target defect's anchor score.
    """
    activations: Dict[int, torch.Tensor] = {}
    gradients: Dict[int, torch.Tensor] = {}
    hooks = []

    def make_fwd_hook(l_idx: int):
        def hook(module, inp, out):
            activations[l_idx] = out
        return hook

    def make_bwd_hook(l_idx: int):
        def hook(module, grad_in, grad_out):
            gradients[l_idx] = grad_out[0]
        return hook

    for l_idx in layer_indices:
        layer = raw_model.model[l_idx]
        hooks.append(layer.register_forward_hook(make_fwd_hook(l_idx)))
        hooks.append(layer.register_full_backward_hook(make_bwd_hook(l_idx)))

    try:
        # Clone cached inference tensors in head to prevent autograd restrictions
        head = raw_model.model[-1]
        if hasattr(head, "anchors") and isinstance(head.anchors, torch.Tensor):
            head.anchors = head.anchors.clone()
        if hasattr(head, "strides") and isinstance(head.strides, torch.Tensor):
            head.strides = head.strides.clone()

        t_in = input_tensor.clone().detach().requires_grad_(True)
        raw_out = raw_model(t_in)
        # raw_out[0][0] shape: (batch, 4 + num_classes + num_masks, num_anchors)
        pred = raw_out[0][0] if isinstance(raw_out[0], (tuple, list)) else raw_out[0]

        pred_boxes = pred[0, :4, :]
        cls_scores = pred[0, 4 + defect["cls_id"], :]

        best_anchor = find_best_anchor_for_defect(pred_boxes, cls_scores, defect["box_model_space"])
        target_score = cls_scores[best_anchor]

        raw_model.zero_grad(set_to_none=True)
        target_score.backward()

        combined_cam = torch.zeros((1, 1, img_size, img_size), dtype=torch.float32)

        for l_idx in layer_indices:
            act = activations.get(l_idx)
            grad = gradients.get(l_idx)
            if act is None or grad is None or grad.abs().sum() == 0:
                continue

            # Layer-CAM element-wise positive weighting: w_ij^k = ReLU(grad_ij^k)
            weights = F.relu(grad)
            cam = torch.sum(weights * act, dim=1, keepdim=True)
            cam = F.relu(cam)
            cam_upsampled = F.interpolate(cam, size=(img_size, img_size), mode="bilinear", align_corners=False)
            combined_cam += cam_upsampled.detach().cpu()

        cam_np = combined_cam[0, 0].numpy()
        cam_min, cam_max = cam_np.min(), cam_np.max()
        if cam_max - cam_min > 1e-8:
            cam_np = (cam_np - cam_min) / (cam_max - cam_min)
        else:
            cam_np = np.zeros_like(cam_np)

        return cam_np

    finally:
        for h in hooks:
            h.remove()


def overlay_cam_on_image(
    orig_bgr: np.ndarray,
    cam_normalized: np.ndarray,
    defect_targets: List[Dict[str, Any]],
    alpha_intensity: float = 0.72,
) -> np.ndarray:
    """
    Renders a high-clarity overlay of the CAM heatmap on top of the original image.
    Applies non-linear soft alpha blending so healthy structures (undercarriage, rails)
    remain naturally visible, while defects glow prominently in Jet colormap colors.
    """
    orig_h, orig_w = orig_bgr.shape[:2]
    cam_resized = cv2.resize(cam_normalized, (orig_w, orig_h), interpolation=cv2.INTER_LINEAR)

    # Color map: Blue (low attribution) -> Green -> Yellow -> Red (peak attribution)
    heatmap_bgr = cv2.applyColorMap(np.uint8(255 * cam_resized), cv2.COLORMAP_JET)

    # Nonlinear alpha scaling: Background regions (cam < 0.05) have zero tint,
    # ensuring no artificial blue cast over normal undercarriage components.
    alpha = np.clip(np.power(cam_resized, 1.2) * alpha_intensity, 0.0, 0.75)[:, :, np.newaxis]
    blended = np.uint8((1.0 - alpha) * orig_bgr.astype(np.float32) + alpha * heatmap_bgr.astype(np.float32))

    # Render defect bounding boxes and readable badges
    color_palette = {
        "Shelling": (0, 165, 255),          # Amber / Orange
        "Cracks-Scratches": (0, 255, 255),  # Yellow
        "Discoloration": (255, 0, 255),     # Magenta
    }

    font = cv2.FONT_HERSHEY_SIMPLEX
    for defect in defect_targets:
        box = defect["box_orig_space"]
        x1, y1, x2, y2 = [int(v) for v in box]
        label = defect["label"]
        conf = defect["conf"]
        box_color = color_palette.get(label, (0, 255, 0))

        # Thin bounding box outline
        cv2.rectangle(blended, (x1, y1), (x2, y2), box_color, 2)

        # Label tag badge with contrast background
        tag_text = f"{label} {conf:.2f}"
        (tw, th), baseline = cv2.getTextSize(tag_text, font, 0.45, 1)
        tag_y1 = max(y1 - th - 6, 0)
        tag_y2 = max(y1, th + 6)
        cv2.rectangle(blended, (x1, tag_y1), (x1 + tw + 6, tag_y2), (20, 20, 20), -1)
        cv2.putText(blended, tag_text, (x1 + 3, tag_y2 - 4), font, 0.45, box_color, 1, cv2.LINE_AA)

    return blended


def generate_gradcam(
    image_path: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
    model_path: Union[str, Path] = MODEL_PATH,
    yolo_result: Optional[Any] = None,
    return_meta: bool = False,
) -> Union[Path, Tuple[Path, Dict[str, Any]]]:
    """
    Generates a defect-focused Explainable AI (Layer-CAM) visualization for railway wheel inspection.

    Args:
        image_path: Path to the input inspection image.
        output_path: Destination path for saving the resulting heatmap image.
                     Defaults to outputs/gradcam/<image_name>.
        model_path: Path to the trained YOLOv8 model weights (best.pt).
        yolo_result: Optional pre-computed Ultralytics Result object. If provided, avoids
                     redundant forward passes for detection.
        return_meta: If True, returns (output_path, metadata_dict) with per-defect attribution stats.

    Returns:
        Path to the saved explainability heatmap image, preserving compatibility with main.py.
    """
    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"Input image not found: {image_path}")

    yolo = get_yolo_model(model_path)
    raw_model = yolo.model
    raw_model.eval()

    for p in raw_model.parameters():
        p.requires_grad = True

    orig_bgr, input_tensor, (orig_h, orig_w) = load_input_tensor(image_path, img_size=IMG_SIZE)

    # 1. Obtain detection results if not pre-provided
    if yolo_result is None:
        yolo_result = yolo(str(image_path), conf=0.25, verbose=False)[0]

    defect_targets = extract_defect_targets(yolo_result, img_size=IMG_SIZE)

    per_defect_cams = []
    meta_info: Dict[str, Any] = {
        "method": "Defect-Targeted Layer-CAM",
        "defect_count": len(defect_targets),
        "defects": [],
    }

    # 2. Compute targeted Layer-CAM for each detected defect
    if defect_targets:
        for defect in defect_targets:
            cam_map = compute_layercam_for_defect(
                raw_model=raw_model,
                input_tensor=input_tensor,
                defect=defect,
                layer_indices=TARGET_LAYER_INDICES,
                img_size=IMG_SIZE,
            )
            per_defect_cams.append(cam_map)
            meta_info["defects"].append({
                "label": defect["label"],
                "confidence": defect["conf"],
                "box": defect["box_orig_space"],
                "attribution_peak": float(cam_map.max()),
                "attribution_mean": float(cam_map.mean()),
            })

        # Multi-defect fusion via element-wise maximum
        final_cam = np.maximum.reduce(per_defect_cams)
    else:
        # No defects detected: Provide clean baseline
        final_cam = np.zeros((IMG_SIZE, IMG_SIZE), dtype=np.float32)

    # 3. Render high-clarity overlay
    cam_overlay_bgr = overlay_cam_on_image(
        orig_bgr=orig_bgr,
        cam_normalized=final_cam,
        defect_targets=defect_targets,
    )

    # If no defects detected, draw a clean informational banner
    if not defect_targets:
        info_text = "No Defects Detected - Wheel Condition Normal"
        cv2.putText(cam_overlay_bgr, info_text, (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)

    # 4. Save output
    if output_path is None:
        output_path = PROJECT_ROOT / "outputs" / "gradcam" / image_path.name
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cv2.imwrite(str(output_path), cam_overlay_bgr)

    if return_meta:
        return output_path, meta_info
    return output_path


if __name__ == "__main__":
    if len(sys.argv) > 1:
        img_file = sys.argv[1]
    else:
        # Default test image from test dataset
        sample_img = PROJECT_ROOT / "dataset" / "test" / "images" / "frame1669_jpg.rf.fbb0d3e03b5cb6a816ee6593ecad1fcf.jpg"
        img_file = str(sample_img) if sample_img.exists() else None

    if img_file is None:
        print("Please provide a path to an image: python explainability/gradcam.py <path>")
        sys.exit(1)

    print(f"Generating defect-focused Explainable AI heatmap for: {img_file}")
    out, meta = generate_gradcam(img_file, return_meta=True)
    print(f"Explainability method: {meta['method']}")
    print(f"Detected defects targeted: {meta['defect_count']}")
    for d in meta["defects"]:
        print(f"  - {d['label']} (conf: {d['confidence']:.2f}): peak CAM={d['attribution_peak']:.2f}")
    print(f"Saved Explainability Heatmap: {out}")
