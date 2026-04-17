import os
import cv2
from fastapi import HTTPException

MAX_IMAGE_BYTES   = 10 * 1024 * 1024   # 10 MB
MAX_VIDEO_BYTES   = 20 * 1024 * 1024   # 20 MB
MAX_VIDEO_SECONDS = 10.0


def validate_image(data: bytes, filename: str = "") -> None:
    size_mb = len(data) / (1024 * 1024)
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"Image '{filename}' is {size_mb:.1f} MB — maximum allowed is {MAX_IMAGE_BYTES // (1024*1024)} MB.",
        )


def validate_video(video_path: str, filename: str = "") -> None:
    size_bytes = os.path.getsize(video_path)
    size_mb = size_bytes / (1024 * 1024)
    if size_bytes > MAX_VIDEO_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"Video '{filename}' is {size_mb:.1f} MB — maximum allowed is {MAX_VIDEO_BYTES // (1024*1024)} MB.",
        )

    cap = cv2.VideoCapture(video_path)
    fps         = cap.get(cv2.CAP_PROP_FPS)
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.release()

    if fps > 0:
        duration_sec = frame_count / fps
        if duration_sec > MAX_VIDEO_SECONDS:
            raise HTTPException(
                status_code=400,
                detail=f"Video '{filename}' is {duration_sec:.1f}s — maximum allowed is {int(MAX_VIDEO_SECONDS)}s.",
            )
