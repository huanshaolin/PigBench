from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import RequestLog


async def save_request_log(
    db: AsyncSession,
    api_key_id: int,
    endpoint: str,
    filename: str,
    file_size_bytes: int,
    result: dict,
    processing_seconds: float,
    uploaded_file_mb: float = 0.0,
    cpu_ms: float = 0.0,
    ram_mb: float = 0.0,
    gpu_percent: float = 0.0,
    vram_mb: float = 0.0,
    cost: float = 0.0,
    pricing_plan_id: Optional[int] = None,
) -> None:
    log = RequestLog(
        api_key_id=api_key_id,
        pricing_plan_id=pricing_plan_id,
        endpoint=endpoint,
        filename=filename,
        file_size_bytes=file_size_bytes,
        result=result,
        processing_seconds=processing_seconds,
        uploaded_file_mb=uploaded_file_mb,
        cpu_ms=cpu_ms,
        ram_mb=ram_mb,
        gpu_percent=gpu_percent,
        vram_mb=vram_mb,
        cost=cost,
    )
    db.add(log)
    await db.commit()
