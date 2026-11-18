import json
from typing import Optional
from datetime import datetime, timezone
from enum import Enum
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import Text


def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OrderType(str, Enum):
    delivery = "delivery"
    pickup = "pickup"


class OrderStatus(str, Enum):
    pending = "pending"
    confirmed = "confirmed"
    preparing = "preparing"
    ready = "ready"
    completed = "completed"
    cancelled = "cancelled"


class Order(SQLModel, table=True):
    __tablename__ = "orders"

    id: Optional[int] = Field(default=None, primary_key=True)
    order_number: str = Field(unique=True, index=True, max_length=20)   # e.g. OM-1042
    tenant_id: int = Field(foreign_key="tenants.id", index=True)
    customer_phone: str = Field(max_length=30, index=True)
    customer_name: Optional[str] = Field(default=None, max_length=120)
    order_type: OrderType = Field(default=OrderType.delivery)
    delivery_address: Optional[str] = Field(default=None, max_length=500)
    status: OrderStatus = Field(default=OrderStatus.pending)
    subtotal: float = Field(default=0.0)
    delivery_fee: float = Field(default=0.0)
    total: float = Field(default=0.0)
    payment_method: str = Field(default="cash_on_delivery", max_length=50)
    notes: Optional[str] = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=get_utc_now)
    updated_at: datetime = Field(default_factory=get_utc_now)


class OrderItem(SQLModel, table=True):
    __tablename__ = "order_items"

    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="orders.id", index=True)
    product_id: Optional[int] = Field(default=None, foreign_key="products.id")
    product_name: str = Field(max_length=150)       # snapshot at time of order
    unit_price: float = Field(ge=0.0)
    quantity: int = Field(ge=1)
    subtotal: float = Field(ge=0.0)


class CartSession(SQLModel, table=True):
    """
    DB-backed per-customer conversation state.
    Keyed by (tenant_id, customer_phone).
    Expires after 2 hours of inactivity.
    """
    __tablename__ = "cart_sessions"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenants.id", index=True)
    customer_phone: str = Field(max_length=30, index=True)
    state_step: str = Field(default="IDLE", max_length=50)
    # Stored as JSON string: [{"product_id": 1, "name": "Mango", "qty": 2, "unit_price": 4.99}]
    cart_items: Optional[str] = Field(default="[]", sa_column=Column(Text))
    selected_type: Optional[str] = Field(default=None, max_length=20)   # "delivery" | "pickup"
    customer_name: Optional[str] = Field(default=None, max_length=120)
    delivery_address: Optional[str] = Field(default=None, max_length=500)
    updated_at: datetime = Field(default_factory=get_utc_now)

    def get_cart(self) -> list:
        return json.loads(self.cart_items or "[]")

    def set_cart(self, items: list):
        self.cart_items = json.dumps(items)
