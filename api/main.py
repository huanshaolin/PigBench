import asyncio
import os
import shutil
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI, File, UploadFile, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse

from pig_detector import load_detection_model, detect_and_annotate
from tracker import load_tracking_detector, track_and_annotate
from cloudinary_upload import upload_image, upload_video
from validation import validate_image, validate_video
from queue_manager import image_queue, video_queue

DEVICE = os.getenv("PIGBENCH_DEVICE", "cuda:0")

models: dict = {}


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[INFO] Loading models on {DEVICE}...")
    models["detector"]          = load_detection_model(DEVICE)
    models["tracking_detector"] = load_tracking_detector(DEVICE)
    print("[INFO] All models loaded and ready.")
    yield
    models.clear()


app = FastAPI(
    title="PigBench API",
    description="Pig detection (image) and tracking (video) API powered by Co-DINO + BoT-SORT",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Global exception handler: queue timeout → 503
# ---------------------------------------------------------------------------
@app.exception_handler(asyncio.TimeoutError)
async def queue_timeout_handler(request, exc: asyncio.TimeoutError):
    return JSONResponse(
        status_code=503,
        content={"detail": str(exc)},
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
def health():
    return {
        "status":        "ok",
        "device":        DEVICE,
        "models_loaded": list(models.keys()),
        "queues": {
            "image": image_queue.status(),
            "video": video_queue.status(),
        },
    }


@app.post("/detect", summary="Detect pigs in an image")
async def detect_pigs(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Image file (jpg, png, etc.)"),
    score_thresh: float = Query(default=0.4, ge=0.0, le=1.0, description="Minimum confidence score"),
):
    """
    Upload an image → detect pigs → return JSON with total count and
    Cloudinary URL of the annotated image.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be an image (image/*).")

    image_bytes = await file.read()
    validate_image(image_bytes, file.filename or "")

    async with image_queue.process():
        total_pigs, annotated_bytes = detect_and_annotate(
            models["detector"], image_bytes, score_thresh
        )
        stem = os.path.splitext(file.filename or "image")[0]
        image_url = upload_image(annotated_bytes, public_id=f"detect_{stem}")

    return {
        "total_pigs":   total_pigs,
        "score_thresh": score_thresh,
        "filename":     file.filename,
        "image_url":    image_url,
    }


@app.post("/track", summary="Track pigs in a video")
async def track_pigs(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Video file (mp4, avi, etc.)"),
    min_conf: float = Query(default=0.1, ge=0.0, le=1.0, description="Minimum detection confidence for tracker"),
):
    """
    Upload a video → run BoT-SORT tracking → return JSON with max pig count
    per frame, per-frame breakdown, and Cloudinary URL of the annotated video.
    """
    if not file.content_type or not file.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be a video (video/*).")

    tmp_dir = tempfile.mkdtemp(prefix="pigbench_")
    background_tasks.add_task(shutil.rmtree, tmp_dir, True)

    input_path  = os.path.join(tmp_dir, file.filename or "input.mp4")
    output_path = os.path.join(tmp_dir, "tracked.mp4")

    with open(input_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    validate_video(input_path, file.filename or "")

    async with video_queue.process():
        stats = track_and_annotate(
            models["tracking_detector"],
            input_path,
            output_path,
            device=DEVICE,
            min_conf=min_conf,
        )
        stem      = os.path.splitext(file.filename or "video")[0]
        video_url = upload_video(output_path, public_id=f"track_{stem}")

    return {
        "max_pigs_in_frame": stats["max_pigs_in_frame"],
        "frame_counts":      stats["frame_counts"],
        "total_frames":      stats["total_frames"],
        "min_conf":          min_conf,
        "filename":          file.filename,
        "video_url":         video_url,
    }
