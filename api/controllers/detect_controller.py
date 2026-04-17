import os
import time

from fastapi import APIRouter, File, UploadFile, HTTPException, Query, BackgroundTasks, Depends, Request
from utils import sanitize_filename
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from db.auth import require_api_key
from db.models import ApiKey
from services.queue_service import image_queue
from services.upload_service import upload_image
from services.log_service import save_request_log
from services.resource_monitor import ResourceMonitor
from services.billing_service import get_active_plan, calculate_cost
from validation.file_validation import validate_image

router = APIRouter()


@router.post("/detect", summary="Detect pigs in an image")
async def detect_pigs(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Image file (jpg, png, etc.)"),
    score_thresh: float = Query(default=0.4, ge=0.0, le=1.0, description="Minimum confidence score"),
    export_file: bool = Query(default=True, description="Upload annotated image to Cloudinary"),
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(require_api_key),
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be an image (image/*).")

    image_bytes = await file.read()
    validate_image(image_bytes, file.filename or "")

    monitor = ResourceMonitor(device=request.app.state.device)
    start   = time.perf_counter()

    async with image_queue.process():
        monitor.start()
        try:
            from services.detection_service import detect_and_annotate
            total_pigs, annotated_bytes = detect_and_annotate(
                request.app.state.detector, image_bytes, score_thresh
            )
            if export_file:
                safe_name        = sanitize_filename(file.filename or "image.jpg")
                stem             = os.path.splitext(safe_name)[0]
                image_url        = upload_image(annotated_bytes, public_id=f"detect_{stem}")
                uploaded_file_mb = round(len(annotated_bytes) / (1024 * 1024), 3)
            else:
                image_url        = None
                uploaded_file_mb = 0.0
        finally:
            resources = monitor.stop()

    processing_seconds = round(time.perf_counter() - start, 2)

    # Billing — chỉ tính khi request thành công
    plan = await get_active_plan(db)
    cost = calculate_cost(plan, uploaded_file_mb, **resources) if plan else 0.0

    response = {
        "total_pigs":         total_pigs,
        "score_thresh":       score_thresh,
        "filename":           file.filename,
        "image_url":          image_url,
        "processing_seconds": processing_seconds,
        "resources":          resources,
        "cost":               cost,
    }

    background_tasks.add_task(
        save_request_log, db,
        api_key_id=api_key.id,
        endpoint="/detect",
        filename=file.filename or "",
        file_size_bytes=len(image_bytes),
        result=response,
        processing_seconds=processing_seconds,
        uploaded_file_mb=uploaded_file_mb,
        cost=cost,
        pricing_plan_id=plan.id if plan else None,
        **resources,
    )

    return response
