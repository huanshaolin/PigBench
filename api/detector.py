import io
import sys
import random
import numpy as np
import cv2
from pathlib import Path
from typing import Tuple

API_DIR = Path(__file__).parent
DETECTION_CONFIG     = str(API_DIR / "../detection/configs/co_detr/co_dino_swin.py")
DETECTION_CHECKPOINT = str(API_DIR / "../detection/data/pretrained_weights/codino_swin.pth")

sys.path.insert(0, str(API_DIR / "../detection/tools/inference"))

# Fixed random seed so colors are consistent between calls
_RNG = random.Random(42)
_COLORS = [(
    _RNG.randint(80, 255),
    _RNG.randint(80, 255),
    _RNG.randint(80, 255),
) for _ in range(512)]


def load_detection_model(device: str = "cuda:0"):
    from mmdet.utils import register_all_modules
    from mmdet.apis import init_detector
    register_all_modules(init_default_scope=False)
    return init_detector(DETECTION_CONFIG, DETECTION_CHECKPOINT, device=device)


def detect_and_annotate(
    model,
    image_bytes: bytes,
    score_thresh: float = 0.4,
) -> Tuple[int, bytes]:
    """
    Run detection on image_bytes, draw bboxes + scores + total count.

    Returns:
        (total_pigs, annotated_jpeg_bytes)
    """
    from mmdet.apis import inference_detector

    # Decode image
    nparr = np.frombuffer(image_bytes, np.uint8)
    image_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

    # Run inference
    result = inference_detector(model, image_rgb)
    scores = result.pred_instances.scores.cpu().numpy()
    bboxes = result.pred_instances.bboxes.cpu().numpy()

    # Draw on a BGR copy
    canvas = image_bgr.copy()
    pig_count = 0

    for idx, (bbox, score) in enumerate(zip(bboxes, scores)):
        if score < score_thresh:
            continue
        pig_count += 1
        x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
        color = _COLORS[idx % len(_COLORS)]

        # Bounding box
        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)

        # Score label
        label = f"{score:.2f}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
        cv2.rectangle(canvas, (x1, y1 - th - 4), (x1 + tw + 2, y1), color, -1)
        cv2.putText(canvas, label, (x1 + 1, y1 - 3),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)

    # Total count overlay (top-left)
    counter_text = f"Total pigs: {pig_count}"
    (cw, ch), _ = cv2.getTextSize(counter_text, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2)
    cv2.rectangle(canvas, (8, 8), (8 + cw + 8, 8 + ch + 10), (0, 0, 0), -1)
    cv2.putText(canvas, counter_text, (12, 8 + ch + 2),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2, cv2.LINE_AA)

    # Encode back to JPEG bytes
    ok, buf = cv2.imencode(".jpg", canvas, [cv2.IMWRITE_JPEG_QUALITY, 92])
    if not ok:
        raise RuntimeError("Failed to encode annotated image to JPEG")

    return pig_count, buf.tobytes()
