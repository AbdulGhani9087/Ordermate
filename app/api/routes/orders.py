from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.db.database import get_session
from app.models.tenant import Tenant
from app.models.order import Order, OrderItem, OrderStatus
from app.schemas.order import OrderResponse, OrderItemResponse, OrderStatusUpdate
from app.api.deps import get_current_tenant

router = APIRouter(prefix="/orders", tags=["Order Management"])


@router.get("", response_model=List[OrderResponse])
def list_orders(
    order_status: Optional[OrderStatus] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    tenant: Tenant = Depends(get_current_tenant),
    session: Session = Depends(get_session),
):
    query = select(Order).where(Order.tenant_id == tenant.id)
    if order_status:
        query = query.where(Order.status == order_status)
    query = query.order_by(Order.created_at.desc()).limit(limit)

    orders = session.exec(query).all()

    result = []
    for order in orders:
        items = session.exec(select(OrderItem).where(OrderItem.order_id == order.id)).all()
        result.append(
            OrderResponse(
                id=order.id,
                order_number=order.order_number,
                tenant_id=order.tenant_id,
                customer_phone=order.customer_phone,
                customer_name=order.customer_name,
                order_type=order.order_type,
                delivery_address=order.delivery_address,
                status=order.status,
                subtotal=order.subtotal,
                delivery_fee=order.delivery_fee,
                total=order.total,
                payment_method=order.payment_method,
                notes=order.notes,
                created_at=order.created_at,
                items=[
                    OrderItemResponse(
                        id=it.id,
                        product_id=it.product_id,
                        product_name=it.product_name,
                        unit_price=it.unit_price,
                        quantity=it.quantity,
                        subtotal=it.subtotal,
                    )
                    for it in items
                ],
            )
        )

    return result


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    session: Session = Depends(get_session),
):
    order = session.get(Order, order_id)
    if not order or order.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Order not found")

    items = session.exec(select(OrderItem).where(OrderItem.order_id == order.id)).all()
    return OrderResponse(
        id=order.id,
        order_number=order.order_number,
        tenant_id=order.tenant_id,
        customer_phone=order.customer_phone,
        customer_name=order.customer_name,
        order_type=order.order_type,
        delivery_address=order.delivery_address,
        status=order.status,
        subtotal=order.subtotal,
        delivery_fee=order.delivery_fee,
        total=order.total,
        payment_method=order.payment_method,
        notes=order.notes,
        created_at=order.created_at,
        items=[
            OrderItemResponse(
                id=it.id,
                product_id=it.product_id,
                product_name=it.product_name,
                unit_price=it.unit_price,
                quantity=it.quantity,
                subtotal=it.subtotal,
            )
            for it in items
        ],
    )


@router.patch("/{order_id}/status", response_model=OrderResponse)
def update_order_status(
    order_id: int,
    req: OrderStatusUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    session: Session = Depends(get_session),
):
    order = session.get(Order, order_id)
    if not order or order.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Order not found")

    order.status = req.status
    session.add(order)
    session.commit()
    session.refresh(order)

    # In Phase 3, this triggers automatic WhatsApp message to customer:
    # "Your order #OM-1042 is now preparing / ready / out for delivery!"

    items = session.exec(select(OrderItem).where(OrderItem.order_id == order.id)).all()
    return OrderResponse(
        id=order.id,
        order_number=order.order_number,
        tenant_id=order.tenant_id,
        customer_phone=order.customer_phone,
        customer_name=order.customer_name,
        order_type=order.order_type,
        delivery_address=order.delivery_address,
        status=order.status,
        subtotal=order.subtotal,
        delivery_fee=order.delivery_fee,
        total=order.total,
        payment_method=order.payment_method,
        notes=order.notes,
        created_at=order.created_at,
        items=[
            OrderItemResponse(
                id=it.id,
                product_id=it.product_id,
                product_name=it.product_name,
                unit_price=it.unit_price,
                quantity=it.quantity,
                subtotal=it.subtotal,
            )
            for it in items
        ],
    )
