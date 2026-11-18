from typing import Optional, List
from pydantic import BaseModel


class TenantProfileUpdate(BaseModel):
    business_name: Optional[str] = None
    contact_phone: Optional[str] = None
    business_category: Optional[str] = None
    country: Optional[str] = None
    currency: Optional[str] = None


class StoreSettingsUpdate(BaseModel):
    delivery_enabled: Optional[bool] = None
    pickup_enabled: Optional[bool] = None
    delivery_fee: Optional[float] = None
    min_order_value: Optional[float] = None
    delivery_eta_mins: Optional[int] = None
    pickup_eta_mins: Optional[int] = None


class StoreHourItem(BaseModel):
    weekday: int
    open_time: Optional[str] = "09:00"
    close_time: Optional[str] = "22:00"
    is_closed: bool = False


class StoreHoursUpdate(BaseModel):
    hours: List[StoreHourItem]


class WhatsAppConfigUpdate(BaseModel):
    phone_number_id: str
    waba_id: str
    access_token: str


class WhatsAppConfigResponse(BaseModel):
    phone_number_id: Optional[str]
    waba_id: Optional[str]
    is_connected: bool
    verify_token: str
    webhook_url: Optional[str]
