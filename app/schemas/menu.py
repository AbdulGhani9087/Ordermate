from typing import Optional, List
from pydantic import BaseModel


class CategoryCreate(BaseModel):
    name: str
    display_order: Optional[int] = 0


class CategoryResponse(BaseModel):
    id: int
    name: str
    display_order: int
    is_active: bool


class ProductCreate(BaseModel):
    category_id: Optional[int] = None
    category_name: Optional[str] = None  # if given, category will be auto-found or created
    name: str
    description: Optional[str] = None
    price: float
    is_available: bool = True
    is_best_seller: bool = False
    image_path: Optional[str] = None


class ProductUpdate(BaseModel):
    category_id: Optional[int] = None
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    is_available: Optional[bool] = None
    is_best_seller: Optional[bool] = None
    image_path: Optional[str] = None


class ProductResponse(BaseModel):
    id: int
    category_id: Optional[int]
    name: str
    description: Optional[str]
    price: float
    is_available: bool
    is_best_seller: bool
    image_path: Optional[str]


class CategoryWithProducts(BaseModel):
    id: int
    name: str
    display_order: int
    products: List[ProductResponse]


class FullMenuResponse(BaseModel):
    categories: List[CategoryWithProducts]
    uncategorized: List[ProductResponse]


class CsvImportResult(BaseModel):
    total_rows: int
    imported: int
    skipped: int
    errors: List[str]
