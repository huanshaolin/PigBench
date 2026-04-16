import cv2
from fastapi import HTTPException

MAX_IMAGE_BYTES = 20 * 1024 * 1024   # 5 MB
MAX_VIDEO_BYTES = 60 * 1024 * 1024  # 20 MB
MAX_VIDEO_SECONDS = 120.0


def validate_image(data: bytes, filename: str = "") -> None:
    """Raise HTTP 400 if image exceeds size limit."""
    size_mb = len(data) / (1024 * 1024)
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"Image '{filename}' is {size_mb:.1f} MB — maximum allowed is 5 MB.",
        )


def validate_video(video_path: str, filename: str = "") -> None:
    """Raise HTTP 400 if video exceeds size or duration limits."""
    # Size check
    import os
    size_bytes = os.path.getsize(video_path)
    size_mb = size_bytes / (1024 * 1024)
    if size_bytes > MAX_VIDEO_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"Video '{filename}' is {size_mb:.1f} MB — maximum allowed is 20 MB.",
        )

    # Duration check
    cap = cv2.VideoCapture(video_path)
    fps         = cap.get(cv2.CAP_PROP_FPS)
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.release()

    if fps > 0:
        duration_sec = frame_count / fps
        if duration_sec > MAX_VIDEO_SECONDS:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Video '{filename}' is {duration_sec:.1f}s — "
                    f"maximum allowed duration is {int(MAX_VIDEO_SECONDS)}s."
                ),
            )
