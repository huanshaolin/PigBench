import os
import sys
import yaml
import numpy as np
import cv2
from pathlib import Path

_API_DIR      = Path(__file__).parent.parent           # api/
DETECTION_DIR = (_API_DIR / "../detection").resolve()
BOXMOT_DIR    = (_API_DIR / "../tracking/boxmot").resolve()

TRACKING_DETECTOR_CONFIG     = str(DETECTION_DIR / "configs/co_detr/co_dino_swin.py")
TRACKING_DETECTOR_CHECKPOINT = str(DETECTION_DIR / "data/pretrained_weights/codino_swin.pth")
TRACKER_CONFIG   = str(BOXMOT_DIR / "configs/trackers/botsort.yaml")
REID_WEIGHTS_DIR = str(BOXMOT_DIR / "reid_weights")
REID_WEIGHTS     = "osnet_x1_0_msmt17.pt"

sys.path.insert(0, str(BOXMOT_DIR))
sys.path.insert(0, str(DETECTION_DIR))

_COLORS = (np.random.RandomState(42).rand(256, 3) * 255).astype(np.int32)


def load_tracking_detector(device: str = "cuda:0"):
    from mmdet.utils import register_all_modules
    from mmdet.apis import init_detector
    register_all_modules(init_default_scope=False)
    return init_detector(TRACKING_DETECTOR_CONFIG, TRACKING_DETECTOR_CHECKPOINT, device=device)


def _load_tracker_defaults() -> dict:
    with open(TRACKER_CONFIG) as f:
        cfg = yaml.safe_load(f)
    return {k: v["default"] for k, v in cfg.items()}


def _ensure_reid_weights() -> Path:
    os.makedirs(REID_WEIGHTS_DIR, exist_ok=True)
    save_path = Path(REID_WEIGHTS_DIR) / REID_WEIGHTS
    if not save_path.exists():
        from boxmot.appearance.reid_model_factory import get_model_url
        import gdown
        url = get_model_url(Path(REID_WEIGHTS))
        if url:
            gdown.download(url, str(save_path), quiet=False)
        else:
            raise RuntimeError(f"No download URL for ReID weights: {REID_WEIGHTS}")
    return save_path


def _draw_frame(frame_bgr: np.ndarray, tracks: np.ndarray, pig_count: int) -> np.ndarray:
    for track in tracks:
        x1, y1, x2, y2 = int(track[0]), int(track[1]), int(track[2]), int(track[3])
        tid   = int(track[4])
        color = tuple(_COLORS[tid % 256].tolist())

        cv2.rectangle(frame_bgr, (x1, y1), (x2, y2), color, 2)
        label = str(tid)
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
        cv2.rectangle(frame_bgr, (x1, y1), (x1 + tw + 4, y1 + th + 6), color, -1)
        cv2.putText(frame_bgr, label, (x1 + 2, y1 + th + 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)

    text = f"Pigs in frame: {pig_count}"
    (cw, ch), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2)
    cv2.rectangle(frame_bgr, (8, 8), (8 + cw + 8, 8 + ch + 10), (0, 0, 0), -1)
    cv2.putText(frame_bgr, text, (12, 8 + ch + 2),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2, cv2.LINE_AA)
    return frame_bgr


def track_and_annotate(detector, video_path: str, output_video_path: str,
                        device: str = "cuda:0", min_conf: float = 0.1) -> dict:
    from mmdet.apis import inference_detector
    from boxmot import create_tracker
    from utils.datasets import VideoDataset

    tracker = create_tracker("botsort", evolve_param_dict=_load_tracker_defaults(),
                              reid_weights=_ensure_reid_weights(), device=device, half=False)

    dataset = VideoDataset(video_path)
    total   = len(dataset)

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
    w   = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h   = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    writer       = cv2.VideoWriter(output_video_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    frame_counts = []

    for idx in range(total):
        if idx % max(1, total // 20) == 0:
            print(f"[INFO] Tracking {(idx+1)*100//total}% ({idx+1}/{total})", flush=True)

        frame_rgb, frame_ori = dataset[idx]
        result  = inference_detector(detector, frame_rgb)
        scores  = result.pred_instances.scores.cpu().numpy()
        bboxes  = result.pred_instances.bboxes.cpu().numpy()

        dets     = [[*bboxes[i], float(scores[i]), 0] for i in range(len(scores)) if scores[i] >= min_conf]
        dets_arr = np.array(dets, dtype=float) if dets else np.empty((0, 6))
        tracks   = tracker.update(dets_arr, frame_rgb)

        frame_counts.append(len(tracks))
        writer.write(_draw_frame(cv2.cvtColor(frame_ori, cv2.COLOR_RGB2BGR), tracks, len(tracks)))

    writer.release()
    return {"max_pigs_in_frame": int(max(frame_counts)) if frame_counts else 0,
            "frame_counts": frame_counts, "total_frames": total}
