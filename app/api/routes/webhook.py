import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlmodel import Session, select

from app.db.database import get_session
from app.models.tenant import Tenant, WhatsAppConfig
from app.services.ai_ordering_engine import AIOrderingEngine
from app.services.whatsapp_service import WhatsAppService

logger = logging.getLogger("webhook")
router = APIRouter(prefix="/webhook", tags=["Meta WhatsApp Webhook"])


@router.get("/{tenant_slug}")
def verify_meta_webhook(
    tenant_slug: str,
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    session: Session = Depends(get_session),
):
    """
    Meta Webhook Verification Handshake.
    When business owner pastes webhook URL into Meta Developer Portal, Meta sends a GET request.
    """
    tenant = session.exec(select(Tenant).where(Tenant.slug == tenant_slug)).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    config = session.exec(select(WhatsAppConfig).where(WhatsAppConfig.tenant_id == tenant.id)).first()
    if not config:
        raise HTTPException(status_code=404, detail="WhatsApp configuration not found")

    if hub_mode == "subscribe" and hub_verify_token == config.verify_token:
        # Return hub.challenge as plain text string
        return Response(content=hub_challenge or "", media_type="text/plain")

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verification token mismatch")


@router.post("/{tenant_slug}")
async def receive_meta_webhook(
    tenant_slug: str,
    request: Request,
    session: Session = Depends(get_session),
):
    """
    Receives real-time customer WhatsApp messages from Meta.
    """
    tenant = session.exec(select(Tenant).where(Tenant.slug == tenant_slug)).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    payload = await request.json()
    logger.info(f"Incoming WhatsApp payload for {tenant_slug}: {payload}")

    try:
        # Navigate standard Meta Graph webhook structure
        entry = payload.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            # Notification or status delivery ping (read, delivered, sent)
            return {"status": "ok", "detail": "acknowledged"}

        msg_obj = messages[0]
        customer_phone = msg_obj.get("from", "")
        msg_type = msg_obj.get("type", "")

        # Extract message content
        incoming_text = ""
        if msg_type == "text":
            incoming_text = msg_obj.get("text", {}).get("body", "")
        elif msg_type == "interactive":
            interactive = msg_obj.get("interactive", {})
            if interactive.get("type") == "button_reply":
                incoming_text = interactive.get("button_reply", {}).get("id", "")
            elif interactive.get("type") == "list_reply":
                incoming_text = interactive.get("list_reply", {}).get("id", "")

        if not incoming_text or not customer_phone:
            return {"status": "ok", "detail": "non-text or empty message"}

        # Process with AI Engine
        result = AIOrderingEngine.process_message(
            tenant=tenant,
            customer_phone=customer_phone,
            message_text=incoming_text,
            db=session,
        )

        # Dispatch response back via WhatsApp
        config = session.exec(select(WhatsAppConfig).where(WhatsAppConfig.tenant_id == tenant.id)).first()
        if config and config.phone_number_id and config.access_token:
            if result.get("buttons"):
                await WhatsAppService.send_interactive_buttons(
                    phone_number_id=config.phone_number_id,
                    access_token=config.access_token,
                    recipient_phone=customer_phone,
                    body_text=result["reply_text"],
                    buttons=result["buttons"],
                )
            else:
                await WhatsAppService.send_text_message(
                    phone_number_id=config.phone_number_id,
                    access_token=config.access_token,
                    recipient_phone=customer_phone,
                    text=result["reply_text"],
                )

        return {"status": "ok", "response": result}

    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return {"status": "error", "message": str(e)}
