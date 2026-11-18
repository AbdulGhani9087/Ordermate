from typing import Optional
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field


def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Tenant(SQLModel, table=True):
    __tablename__ = "tenants"

    id: Optional[int] = Field(default=None, primary_key=True)
    slug: str = Field(unique=True, index=True, max_length=60)
    business_name: str = Field(max_length=120)
    owner_email: str = Field(unique=True, index=True, max_length=255)
    hashed_password: str
    contact_phone: Optional[str] = Field(default=None, max_length=30)
    business_category: Optional[str] = Field(default=None, max_length=80)
    country: Optional[str] = Field(default=None, max_length=60)
    currency: str = Field(default="USD", max_length=10)
    is_verified: bool = Field(default=False)
    is_active: bool = Field(default=True)
    is_live: bool = Field(default=False)
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)


class WhatsAppConfig(SQLModel, table=True):
    __tablename__ = "whatsapp_configs"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenants.id", unique=True, index=True)
    phone_number_id: Optional[str] = Field(default=None, max_length=50)
    waba_id: Optional[str] = Field(default=None, max_length=50)
    access_token: Optional[str] = Field(default=None)   # stored encrypted in production
    verify_token: str = Field(max_length=80)             # generated per tenant
    webhook_url: Optional[str] = Field(default=None, max_length=255)
    is_connected: bool = Field(default=False)
    updated_at: datetime = Field(default_factory=get_utc_now)


class StoreSettings(SQLModel, table=True):
    __tablename__ = "store_settings"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenants.id", unique=True, index=True)
    delivery_enabled: bool = Field(default=True)
    pickup_enabled: bool = Field(default=True)
    delivery_fee: float = Field(default=0.0)
    min_order_value: float = Field(default=0.0)
    delivery_eta_mins: int = Field(default=30)
    pickup_eta_mins: int = Field(default=15)
    updated_at: datetime = Field(default_factory=get_utc_now)


class StoreHours(SQLModel, table=True):
    __tablename__ = "store_hours"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenants.id", index=True)
    weekday: int = Field(ge=0, le=6)        # 0=Monday … 6=Sunday
    open_time: Optional[str] = Field(default="09:00")   # "HH:MM"
    close_time: Optional[str] = Field(default="22:00")  # "HH:MM"
    is_closed: bool = Field(default=False)
