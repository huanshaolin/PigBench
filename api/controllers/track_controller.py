import os
import shutil
import tempfile
import time

from fastapi import APIRouter, File, UploadFile, HTTPException, Query, BackgroundTasks, Depends, Request
from utils import sanitize_filename
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from db.auth import require_api_key
from db.models import ApiKey
from services.queue_service import video_queue
from services.upload_service import upload_video
from services.log_service import save_request_log
from services.resource_monitor import ResourceMonitor
from services.billing_service import get_active_plan, calculate_cost
from validation.file_validation import validate_video

router = APIRouter()


@router.post("/track", summary="Track pigs in a video")
async def track_pigs(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Video file (mp4, avi, etc.)"),
    min_conf: float = Query(default=0.1, ge=0.0, le=1.0, description="Minimum detection confidence"),
    export_file: bool = Query(default=True, description="Upload annotated video to Cloudinary"),
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(require_api_key),
):
    if not file.content_type or not file.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be a video (video/*).")

    tmp_dir     = tempfile.mkdtemp(prefix="pigbench_")
    input_path  = os.path.join(tmp_dir, file.filename or "input.mp4")
    output_path = os.path.join(tmp_dir, "tracked.mp4")
    background_tasks.add_task(shutil.rmtree, tmp_dir, True)

    with open(input_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    validate_video(input_path, file.filename or "")

    file_size = os.path.getsize(input_path)
    monitor   = ResourceMonitor(device=request.app.state.device)
    start     = time.perf_counter()

    async with video_queue.process():
        monitor.start()
        try:
            from services.tracking_service import track_and_annotate
            stats = track_and_annotate(
                request.app.state.tracking_detector,
                input_path, output_path,
                device=request.app.state.device,
                min_conf=min_conf,
            )
            if export_file:
                safe_name        = sanitize_filename(file.filename or "video.mp4")
                stem             = os.path.splitext(safe_name)[0]
                video_url        = upload_video(output_path, public_id=f"track_{stem}")
                uploaded_file_mb = round(os.path.getsize(output_path) / (1024 * 1024), 3)
            else:
                video_url        = None
                uploaded_file_mb = 0.0
        finally:
            resources = monitor.stop()

    processing_seconds = round(time.perf_counter() - start, 2)

    # Billing — chỉ tính khi request thành công
    plan = await get_active_plan(db)
    cost = calculate_cost(plan, uploaded_file_mb, **resources) if plan else 0.0

    response = {
        "max_pigs_in_frame":  stats["max_pigs_in_frame"],
        "frame_counts":       stats["frame_counts"],
        "total_frames":       stats["total_frames"],
        "min_conf":           min_conf,
        "filename":           file.filename,
        "video_url":          video_url,
        "processing_seconds": processing_seconds,
        "resources":          resources,
        "cost":               cost,
    }

    background_tasks.add_task(
        save_request_log, db,
        api_key_id=api_key.id,
        endpoint="/track",
        filename=file.filename or "",
        file_size_bytes=file_size,
        result=response,
        processing_seconds=processing_seconds,
        uploaded_file_mb=uploaded_file_mb,
        cost=cost,
        pricing_plan_id=plan.id if plan else None,
        **resources,
    )

    return response
