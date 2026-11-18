import re
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.db.database import get_session
from app.core.security import hash_password, verify_password, create_access_token, generate_verify_token
from app.models.tenant import Tenant, StoreSettings, WhatsAppConfig, StoreHours
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, TenantResponse
from app.api.deps import get_current_tenant

router = APIRouter(prefix="/auth", tags=["Authentication"])


def generate_slug(name: str, session: Session) -> str:
    base_slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not base_slug:
        base_slug = "store"
    slug = base_slug
    counter = 1
    while session.exec(select(Tenant).where(Tenant.slug == slug)).first():
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest, session: Session = Depends(get_session)):
    # Check email uniqueness
    existing = session.exec(select(Tenant).where(Tenant.owner_email == req.owner_email)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists",
        )

    slug = generate_slug(req.business_name, session)

    tenant = Tenant(
        slug=slug,
        business_name=req.business_name,
        owner_email=req.owner_email,
        hashed_password=hash_password(req.password),
        contact_phone=req.contact_phone,
        business_category=req.business_category,
        currency=req.currency or "USD",
        is_verified=False,
        is_active=True,
        is_live=False,
    )
    session.add(tenant)
    session.commit()
    session.refresh(tenant)

    # Initialize default store settings
    settings = StoreSettings(tenant_id=tenant.id)
    session.add(settings)

    # Initialize WhatsApp config with unique verify token & webhook URL
    wa_config = WhatsAppConfig(
        tenant_id=tenant.id,
        verify_token=generate_verify_token(),
        webhook_url=f"/api/v1/webhook/{tenant.slug}",
    )
    session.add(wa_config)

    # Initialize standard store hours (Monday=0 to Sunday=6, open 09:00 - 22:00)
    for day in range(7):
        hours = StoreHours(tenant_id=tenant.id, weekday=day, open_time="09:00", close_time="22:00", is_closed=False)
        session.add(hours)

    session.commit()

    token = create_access_token({"sub": tenant.owner_email, "tenant_id": tenant.id})
    return TokenResponse(
        access_token=token,
        tenant_id=tenant.id,
        slug=tenant.slug,
        business_name=tenant.business_name,
    )


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, session: Session = Depends(get_session)):
    tenant = session.exec(select(Tenant).where(Tenant.owner_email == req.email)).first()
    if not tenant or not verify_password(req.password, tenant.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not tenant.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    token = create_access_token({"sub": tenant.owner_email, "tenant_id": tenant.id})
    return TokenResponse(
        access_token=token,
        tenant_id=tenant.id,
        slug=tenant.slug,
        business_name=tenant.business_name,
    )


@router.get("/me", response_model=TenantResponse)
def get_me(tenant: Tenant = Depends(get_current_tenant)):
    return TenantResponse(
        id=tenant.id,
        slug=tenant.slug,
        business_name=tenant.business_name,
        owner_email=tenant.owner_email,
        contact_phone=tenant.contact_phone,
        business_category=tenant.business_category,
        currency=tenant.currency,
        is_verified=tenant.is_verified,
        is_active=tenant.is_active,
        is_live=tenant.is_live,
    )


@router.post("/verify-email")
def verify_email(tenant: Tenant = Depends(get_current_tenant), session: Session = Depends(get_session)):
    tenant.is_verified = True
    session.add(tenant)
    session.commit()
    return {"message": "Email verified successfully", "is_verified": True}
