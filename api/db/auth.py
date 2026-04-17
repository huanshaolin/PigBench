from fastapi import Header, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.database import get_db
from db.models import ApiKey


async def require_api_key(
    x_api_key: str = Header(..., alias="X-API-Key", description="API key cấp cho người dùng"),
    db: AsyncSession = Depends(get_db),
) -> ApiKey:
    result = await db.execute(select(ApiKey).where(ApiKey.key == x_api_key))
    api_key = result.scalar_one_or_none()

    if api_key is None or not api_key.is_active:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key.")

    return api_key
