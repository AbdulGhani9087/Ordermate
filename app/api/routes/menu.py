import csv
import io
import re
import uuid
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlmodel import Session, select

from app.db.database import get_session
from app.models.tenant import Tenant
from app.models.menu import Category, Product
from app.schemas.menu import (
    CategoryCreate,
    CategoryResponse,
    CategoryWithProducts,
    FullMenuResponse,
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    CsvImportResult,
)
from app.api.deps import get_current_tenant

router = APIRouter(prefix="/menu", tags=["Menu Management"])

STATIC_DIR = Path(__file__).resolve().parents[2] / "static"


@router.get("", response_model=FullMenuResponse)
def get_menu(
    tenant: Tenant = Depends(get_current_tenant),
    session: Session = Depends(get_session),
):
    categories = session.exec(
        select(Category)
        .where(Category.tenant_id == tenant.id)
        .order_by(Category.display_order, Category.name)
    ).all()

    category_list = []
    for cat in categories:
        products = session.exec(
            select(Product)
            .where(Product.tenant_id == tenant.id)
            .where(Product.category_id == cat.id)
        ).all()
        category_list.append(
            CategoryWithProducts(
                id=cat.id,
                name=cat.name,
                display_order=cat.display_order,
                products=[
                    ProductResponse(
                        id=p.id,
                        category_id=p.category_id,
                        name=p.name,
                        description=p.description,
                        price=p.price,
                        is_available=p.is_available,
                        is_best_seller=p.is_best_seller,
                        image_path=p.image_path,
                    )
                    for p in products
                ],
            )
        )

    # Uncategorized products
    uncategorized = session.exec(
        select(Product)
        .where(Product.tenant_id == tenant.id)
        .where(Product.category_id == None)
    ).all()

    return FullMenuResponse(
        categories=category_list,
        uncategorized=[
            ProductResponse(
                id=p.id,
                category_id=p.category_id,
                name=p.name,
                description=p.description,
                price=p.price,
                is_available=p.is_available,
                is_best_seller=p.is_best_seller,
                image_path=p.image_path,
            )
            for p in uncategorized
        ],
    )


@router.post("/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    req: CategoryCreate,
    tenant: Tenant = Depends(get_current_tenant),
    session: Session = Depends(get_session),
):
    cat = Category(
        tenant_id=tenant.id,
        name=req.name.strip(),
        display_order=req.display_order or 0,
    )
    session.add(cat)
    session.commit()
    session.refresh(cat)
    return cat


@router.delete("/categories/{category_id}")
def delete_category(
    category_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    session: Session = Depends(get_session),
):
    cat = session.get(Category, category_id)
    if not cat or cat.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Category not found")

    # Set products category_id to None
    products = session.exec(select(Product).where(Product.category_id == category_id)).all()
    for p in products:
        p.category_id = None
        session.add(p)

    session.delete(cat)
    session.commit()
    return {"message": "Category deleted successfully"}


@router.post("/items", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    req: ProductCreate,
    tenant: Tenant = Depends(get_current_tenant),
    session: Session = Depends(get_session),
):
    cat_id = req.category_id
    if req.category_name and not cat_id:
        existing_cat = session.exec(
            select(Category)
            .where(Category.tenant_id == tenant.id)
            .where(Category.name.ilike(req.category_name.strip()))
        ).first()
        if existing_cat:
            cat_id = existing_cat.id
        else:
            new_cat = Category(tenant_id=tenant.id, name=req.category_name.strip())
            session.add(new_cat)
            session.commit()
            session.refresh(new_cat)
            cat_id = new_cat.id

    product = Product(
        tenant_id=tenant.id,
        category_id=cat_id,
        name=req.name.strip(),
        description=req.description,
        price=req.price,
        is_available=req.is_available,
        is_best_seller=req.is_best_seller,
        image_path=req.image_path,
    )
    session.add(product)
    session.commit()
    session.refresh(product)
    return product


@router.put("/items/{item_id}", response_model=ProductResponse)
def update_product(
    item_id: int,
    req: ProductUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    session: Session = Depends(get_session),
):
    product = session.get(Product, item_id)
    if not product or product.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Product not found")

    if req.category_id is not None:
        product.category_id = req.category_id
    if req.name is not None:
        product.name = req.name.strip()
    if req.description is not None:
        product.description = req.description
    if req.price is not None:
        product.price = req.price
    if req.is_available is not None:
        product.is_available = req.is_available
    if req.is_best_seller is not None:
        product.is_best_seller = req.is_best_seller
    if req.image_path is not None:
        product.image_path = req.image_path

    session.add(product)
    session.commit()
    session.refresh(product)
    return product


@router.delete("/items/{item_id}")
def delete_product(
    item_id: int,
    tenant: Tenant = Depends(get_current_tenant),
    session: Session = Depends(get_session),
):
    product = session.get(Product, item_id)
    if not product or product.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Product not found")

    session.delete(product)
    session.commit()
    return {"message": "Product deleted successfully"}


@router.post("/upload-csv", response_model=CsvImportResult)
async def upload_menu_csv(
    file: UploadFile = File(...),
    tenant: Tenant = Depends(get_current_tenant),
    session: Session = Depends(get_session),
):
    """
    Bulk imports menu from a CSV file.
    Expected header: category,name,price,description,is_best_seller,image_url
    """
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are supported")

    content = await file.read()
    try:
        text = content.decode("utf-8-sig")  # handles potential BOM
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV file is empty or corrupted")

    # Normalize column headers to lowercase
    field_map = {col.lower().strip(): col for col in reader.fieldnames}

    total_rows = 0
    imported = 0
    skipped = 0
    errors = []

    # Cache categories by name to avoid repeated queries
    cat_cache = {
        cat.name.lower(): cat.id
        for cat in session.exec(select(Category).where(Category.tenant_id == tenant.id)).all()
    }

    for row_idx, raw_row in enumerate(reader, start=1):
        total_rows += 1
        row = {k.lower().strip(): v.strip() for k, v in raw_row.items() if k}

        name = row.get("name") or row.get("item") or row.get("product_name")
        price_str = row.get("price") or row.get("rate")
        category_name = row.get("category") or "General"
        description = row.get("description") or None
        is_best_seller_raw = row.get("is_best_seller") or row.get("best_seller") or "false"
        is_best_seller = is_best_seller_raw.lower() in ("true", "1", "yes", "y")
        image_url = row.get("image_url") or row.get("image") or None

        if not name or not price_str:
            skipped += 1
            errors.append(f"Row {row_idx}: Missing required name or price")
            continue

        try:
            # Clean price string like "$4.99" -> 4.99
            price = float(re.sub(r"[^\d.]", "", price_str))
        except ValueError:
            skipped += 1
            errors.append(f"Row {row_idx} ({name}): Invalid price '{price_str}'")
            continue

        # Get or create category
        cat_key = category_name.lower().strip()
        if cat_key in cat_cache:
            category_id = cat_cache[cat_key]
        else:
            new_cat = Category(tenant_id=tenant.id, name=category_name.strip())
            session.add(new_cat)
            session.commit()
            session.refresh(new_cat)
            cat_cache[cat_key] = new_cat.id
            category_id = new_cat.id

        product = Product(
            tenant_id=tenant.id,
            category_id=category_id,
            name=name,
            description=description,
            price=price,
            is_available=True,
            is_best_seller=is_best_seller,
            image_path=image_url,
        )
        session.add(product)
        imported += 1

    session.commit()

    return CsvImportResult(
        total_rows=total_rows,
        imported=imported,
        skipped=skipped,
        errors=errors,
    )


@router.post("/upload-item-image")
async def upload_item_image(
    file: UploadFile = File(...),
    tenant: Tenant = Depends(get_current_tenant),
):
    """
    Uploads a product picture and saves it under static/uploads/{tenant_id}/products/.
    """
    allowed_extensions = {".jpg", ".jpeg", ".png", ".webp"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported image type. Allowed: {', '.join(allowed_extensions)}",
        )

    tenant_folder = STATIC_DIR / "uploads" / str(tenant.id) / "products"
    tenant_folder.mkdir(parents=True, exist_ok=True)

    file_id = f"{uuid.uuid4().hex[:12]}{ext}"
    target_path = tenant_folder / file_id

    content = await file.read()
    with open(target_path, "wb") as f:
        f.write(content)

    rel_url = f"/static/uploads/{tenant.id}/products/{file_id}"
    return {"image_path": rel_url, "filename": file.filename}
