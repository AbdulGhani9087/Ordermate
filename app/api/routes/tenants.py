from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import List

from app.db.database import get_session
from app.models.tenant import Tenant, StoreSettings, WhatsAppConfig, StoreHours
from app.schemas.tenant import (
    TenantProfileUpdate,
    StoreSettingsUpdate,
    StoreHoursUpdate,
    StoreHourItem,
    WhatsAppConfigUpdate,
    WhatsAppConfigResponse,
)
from app.schemas.auth import TenantResponse
from app.api.deps import get_current_tenant

router = APIRouter(prefix="/tenants", tags=["Business Profile & Settings"])


@router.get("/profile", response_model=TenantResponse)
def get_profile(tenant: Tenant = Depends(get_current_tenant)):
    return tenant


@router.put("/profile", response_model=TenantResponse)
def update_profile(
    req: TenantProfileUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    session: Session = Depends(get_session),
):
    if req.business_name is not None:
        tenant.business_name = req.business_name
    if req.contact_phone is not None:
        tenant.contact_phone = req.contact_phone
    if req.business_category is not None:
        tenant.business_category = req.business_category
    if req.country is not None:
        tenant.country = req.country
    if req.currency is not None:
        tenant.currency = req.currency

    session.add(tenant)
    session.commit()
    session.refresh(tenant)
    return tenant


@router.get("/settings")
def get_settings(
    tenant: Tenant = Depends(get_current_tenant),
    session: Session = Depends(get_session),
):
    settings = session.exec(select(StoreSettings).where(StoreSettings.tenant_id == tenant.id)).first()
    if not settings:
        settings = StoreSettings(tenant_id=tenant.id)
        session.add(settings)
        session.commit()
        session.refresh(settings)
    return settings


@router.put("/settings")
def update_settings(
    req: StoreSettingsUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    session: Session = Depends(get_session),
):
    settings = session.exec(select(StoreSettings).where(StoreSettings.tenant_id == tenant.id)).first()
    if not settings:
        settings = StoreSettings(tenant_id=tenant.id)

    if req.delivery_enabled is not None:
        settings.delivery_enabled = req.delivery_enabled
    if req.pickup_enabled is not None:
        settings.pickup_enabled = req.pickup_enabled
    if req.delivery_fee is not None:
        settings.delivery_fee = req.delivery_fee
    if req.min_order_value is not None:
        settings.min_order_value = req.min_order_value
    if req.delivery_eta_mins is not None:
        settings.delivery_eta_mins = req.delivery_eta_mins
    if req.pickup_eta_mins is not None:
        settings.pickup_eta_mins = req.pickup_eta_mins

    session.add(settings)
    session.commit()
    session.refresh(settings)
    return settings


@router.get("/hours", response_model=List[StoreHourItem])
def get_hours(
    tenant: Tenant = Depends(get_current_tenant),
    session: Session = Depends(get_session),
):
    hours = session.exec(
        select(StoreHours).where(StoreHours.tenant_id == tenant.id).order_by(StoreHours.weekday)
    ).all()
    return hours


@router.put("/hours")
def update_hours(
    req: StoreHoursUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    session: Session = Depends(get_session),
):
    for item in req.hours:
        existing = session.exec(
            select(StoreHours)
            .where(StoreHours.tenant_id == tenant.id)
            .where(StoreHours.weekday == item.weekday)
        ).first()

        if existing:
            existing.open_time = item.open_time
            existing.close_time = item.close_time
            existing.is_closed = item.is_closed
            session.add(existing)
        else:
            new_hour = StoreHours(
                tenant_id=tenant.id,
                weekday=item.weekday,
                open_time=item.open_time,
                close_time=item.close_time,
                is_closed=item.is_closed,
            )
            session.add(new_hour)

    session.commit()
    return {"message": "Store hours updated successfully"}


@router.get("/whatsapp-config", response_model=WhatsAppConfigResponse)
def get_whatsapp_config(
    tenant: Tenant = Depends(get_current_tenant),
    session: Session = Depends(get_session),
):
    config = session.exec(select(WhatsAppConfig).where(WhatsAppConfig.tenant_id == tenant.id)).first()
    if not config:
        raise HTTPException(status_code=404, detail="WhatsApp config not found")
    return WhatsAppConfigResponse(
        phone_number_id=config.phone_number_id,
        waba_id=config.waba_id,
        is_connected=config.is_connected,
        verify_token=config.verify_token,
        webhook_url=config.webhook_url,
    )


@router.post("/whatsapp-config", response_model=WhatsAppConfigResponse)
def update_whatsapp_config(
    req: WhatsAppConfigUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    session: Session = Depends(get_session),
):
    config = session.exec(select(WhatsAppConfig).where(WhatsAppConfig.tenant_id == tenant.id)).first()
    if not config:
        config = WhatsAppConfig(tenant_id=tenant.id, verify_token="token")

    config.phone_number_id = req.phone_number_id.strip()
    config.waba_id = req.waba_id.strip()
    config.access_token = req.access_token.strip()
    config.is_connected = bool(req.phone_number_id and req.access_token)

    session.add(config)
    session.commit()
    session.refresh(config)

    return WhatsAppConfigResponse(
        phone_number_id=config.phone_number_id,
        waba_id=config.waba_id,
        is_connected=config.is_connected,
        verify_token=config.verify_token,
        webhook_url=config.webhook_url,
    )


@router.post("/toggle-live")
def toggle_live(
    tenant: Tenant = Depends(get_current_tenant),
    session: Session = Depends(get_session),
):
    tenant.is_live = not tenant.is_live
    session.add(tenant)
    session.commit()
    return {"is_live": tenant.is_live, "message": "Store is now live" if tenant.is_live else "Store is offline"}
