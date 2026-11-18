from typing import Optional
from pydantic import BaseModel


class RegisterRequest(BaseModel):
    business_name: str
    owner_email: str
    password: str
    contact_phone: Optional[str] = None
    business_category: Optional[str] = "Juice Bar & Beverages"
    currency: Optional[str] = "USD"


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    tenant_id: int
    slug: str
    business_name: str


class TenantResponse(BaseModel):
    id: int
    slug: str
    business_name: str
    owner_email: str
    contact_phone: Optional[str]
    business_category: Optional[str]
    currency: str
    is_verified: bool
    is_active: bool
    is_live: bool
