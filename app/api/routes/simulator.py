from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db.database import get_session
from app.models.tenant import Tenant
from app.models.order import CartSession
from app.services.ai_ordering_engine import AIOrderingEngine

router = APIRouter(prefix="/simulator", tags=["WhatsApp Simulator"])


class SimulatorChatRequest(BaseModel):
    customer_phone: Optional[str] = "+923001234567"
    message: str


class SimulatorChatResponse(BaseModel):
    reply_text: str
    buttons: Optional[List[Dict[str, str]]] = None
    order_id: Optional[int] = None
    order_number: Optional[str] = None


@router.post("/{tenant_slug}/chat", response_model=SimulatorChatResponse)
def simulator_chat(
    tenant_slug: str,
    req: SimulatorChatRequest,
    session: Session = Depends(get_session),
):
    """
    Test WhatsApp conversational ordering in real time from the web dashboard.
    """
    tenant = session.exec(select(Tenant).where(Tenant.slug == tenant_slug)).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant store not found")

    result = AIOrderingEngine.process_message(
        tenant=tenant,
        customer_phone=req.customer_phone or "+923001234567",
        message_text=req.message,
        db=session,
    )

    return SimulatorChatResponse(
        reply_text=result["reply_text"],
        buttons=result.get("buttons"),
        order_id=result.get("order_id"),
        order_number=result.get("order_number"),
    )


@router.post("/{tenant_slug}/reset")
def simulator_reset(
    tenant_slug: str,
    customer_phone: Optional[str] = "+923001234567",
    session: Session = Depends(get_session),
):
    """
    Resets the test customer cart session.
    """
    tenant = session.exec(select(Tenant).where(Tenant.slug == tenant_slug)).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant store not found")

    cart_sess = session.exec(
        select(CartSession)
        .where(CartSession.tenant_id == tenant.id)
        .where(CartSession.customer_phone == customer_phone)
    ).first()

    if cart_sess:
        cart_sess.state_step = "IDLE"
        cart_sess.set_cart([])
        cart_sess.selected_type = None
        cart_sess.delivery_address = None
        session.add(cart_sess)
        session.commit()

    return {"message": "Simulator conversation reset successfully"}
