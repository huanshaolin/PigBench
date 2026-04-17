from datetime import datetime
from typing import Optional
from sqlalchemy import String, Boolean, Integer, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.database import Base


class PricingPlan(Base):
    __tablename__ = "pricing_plans"

    id:   Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)

    # Base price per successful request
    price_per_request:    Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Price per unit of resource consumed
    price_per_upload_mb:  Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    price_per_cpu_ms:     Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    price_per_ram_mb:     Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    price_per_gpu_pct:    Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    price_per_vram_mb:    Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Validity window
    valid_from:  Mapped[datetime]           = mapped_column(DateTime, nullable=False)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)  # null = indefinite

    is_active:   Mapped[bool]     = mapped_column(Boolean, default=True, nullable=False)
    created_at:  Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    logs: Mapped[list["RequestLog"]] = relationship(back_populates="pricing_plan")


class ApiKey(Base):
    __tablename__ = "api_keys"

    id:         Mapped[int]      = mapped_column(Integer, primary_key=True)
    key:        Mapped[str]      = mapped_column(String(64), unique=True, nullable=False, index=True)
    user_name:  Mapped[str]      = mapped_column(String(128), nullable=False)
    is_active:  Mapped[bool]     = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    logs: Mapped[list["RequestLog"]] = relationship(back_populates="api_key")


class RequestLog(Base):
    __tablename__ = "request_logs"

    id:                 Mapped[int]           = mapped_column(Integer, primary_key=True)
    api_key_id:         Mapped[int]           = mapped_column(ForeignKey("api_keys.id"), nullable=False)
    pricing_plan_id:    Mapped[Optional[int]] = mapped_column(ForeignKey("pricing_plans.id"), nullable=True)
    endpoint:           Mapped[str]           = mapped_column(String(32),  nullable=False)
    filename:           Mapped[str]           = mapped_column(String(256), nullable=False)
    file_size_bytes:    Mapped[int]           = mapped_column(Integer,     nullable=False)
    result:             Mapped[dict]          = mapped_column(JSON,        nullable=False)
    processing_seconds: Mapped[float]         = mapped_column(Float,       nullable=False)

    # Cloudinary upload (0.0 nếu không export)
    uploaded_file_mb:   Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Resource usage
    cpu_ms:      Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ram_mb:      Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    gpu_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    vram_mb:     Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Billing — 0.0 nếu request thất bại
    cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    api_key:      Mapped["ApiKey"]           = relationship(back_populates="logs")
    pricing_plan: Mapped[Optional["PricingPlan"]] = relationship(back_populates="logs")
