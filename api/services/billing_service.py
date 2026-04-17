from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from db.models import PricingPlan


async def get_active_plan(db: AsyncSession) -> Optional[PricingPlan]:
    """
    Trả về pricing plan đang có hiệu lực tại thời điểm hiện tại.
    - is_active = true
    - valid_from <= now
    - valid_until IS NULL hoặc valid_until >= now
    Nếu nhiều plan cùng hợp lệ, lấy plan bắt đầu gần nhất.
    """
    now = datetime.utcnow()
    result = await db.execute(
        select(PricingPlan)
        .where(
            and_(
                PricingPlan.is_active == True,
                PricingPlan.valid_from <= now,
                or_(PricingPlan.valid_until == None, PricingPlan.valid_until >= now),
            )
        )
        .order_by(PricingPlan.valid_from.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def calculate_cost(
    plan: PricingPlan,
    uploaded_file_mb: float,
    cpu_ms: float,
    ram_mb: float,
    gpu_percent: float,
    vram_mb: float,
) -> float:
    """
    Tính tổng chi phí của 1 request thành công dựa trên bảng giá.

    cost = price_per_request
         + price_per_upload_mb  * uploaded_file_mb
         + price_per_cpu_ms     * cpu_ms
         + price_per_ram_mb     * ram_mb
         + price_per_gpu_pct    * gpu_percent
         + price_per_vram_mb    * vram_mb
    """
    cost = (
        plan.price_per_request
        + plan.price_per_upload_mb * uploaded_file_mb
        + plan.price_per_cpu_ms    * cpu_ms
        + plan.price_per_ram_mb    * ram_mb
        + plan.price_per_gpu_pct   * gpu_percent
        + plan.price_per_vram_mb   * vram_mb
    )
    return round(cost, 6)
