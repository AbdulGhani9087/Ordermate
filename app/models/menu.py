from typing import Optional
from sqlmodel import SQLModel, Field


class Category(SQLModel, table=True):
    __tablename__ = "categories"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenants.id", index=True)
    name: str = Field(max_length=100)
    display_order: int = Field(default=0)
    is_active: bool = Field(default=True)


class Product(SQLModel, table=True):
    __tablename__ = "products"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenants.id", index=True)
    category_id: Optional[int] = Field(default=None, foreign_key="categories.id")
    name: str = Field(max_length=150)
    description: Optional[str] = Field(default=None, max_length=500)
    price: float = Field(ge=0.0)
    is_available: bool = Field(default=True)
    is_best_seller: bool = Field(default=False)
    image_path: Optional[str] = Field(default=None, max_length=255)  # relative path under /static/uploads/
