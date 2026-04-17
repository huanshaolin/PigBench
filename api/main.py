import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from services.detection_service import load_detection_model
from services.tracking_service import load_tracking_detector
from services.queue_service import image_queue, video_queue
from controllers.detect_controller import router as detect_router
from controllers.track_controller import router as track_router

DEVICE = os.getenv("PIGBENCH_DEVICE", "cuda:0")


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[INFO] Loading models on {DEVICE}...")
    app.state.device             = DEVICE
    app.state.detector           = load_detection_model(DEVICE)
    app.state.tracking_detector  = load_tracking_detector(DEVICE)
    print("[INFO] All models loaded and ready.")
    yield
    del app.state.detector
    del app.state.tracking_detector


app = FastAPI(
    title="PigBench API",
    description="Pig detection (image) and tracking (video) API powered by Co-DINO + BoT-SORT",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(asyncio.TimeoutError)
async def queue_timeout_handler(request, exc: asyncio.TimeoutError):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.get("/health")
def health():
    return {
        "status":        "ok",
        "device":        DEVICE,
        "queues": {
            "image": image_queue.status(),
            "video": video_queue.status(),
        },
    }


app.include_router(detect_router)
app.include_router(track_router)
