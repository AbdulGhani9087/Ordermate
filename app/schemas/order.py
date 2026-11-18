from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
from app.models.order import OrderStatus, OrderType


class OrderItemResponse(BaseModel):
    id: int
    product_id: Optional[int]
    product_name: str
    unit_price: float
    quantity: int
    subtotal: float


class OrderResponse(BaseModel):
    id: int
    order_number: str
    tenant_id: int
    customer_phone: str
    customer_name: Optional[str]
    order_type: OrderType
    delivery_address: Optional[str]
    status: OrderStatus
    subtotal: float
    delivery_fee: float
    total: float
    payment_method: str
    notes: Optional[str]
    created_at: datetime
    items: List[OrderItemResponse] = []


class OrderStatusUpdate(BaseModel):
    status: OrderStatus
