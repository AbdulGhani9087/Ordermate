"""
Phase 1 Tests — Database Models & Core Security
"""
import pytest
from sqlmodel import SQLModel, create_engine, Session

# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite://"


@pytest.fixture(name="session")
def session_fixture():
    """Create a fresh in-memory DB for each test."""
    # Import all models so SQLModel registers them
    import app.models  # noqa: F401
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


# ── Tenant model ──────────────────────────────────────────────────────────────
def test_create_tenant(session):
    from app.models import Tenant
    tenant = Tenant(
        slug="juice-island",
        business_name="Juice Island",
        owner_email="owner@juiceisland.com",
        hashed_password="hashed123",
        currency="USD",
    )
    session.add(tenant)
    session.commit()
    session.refresh(tenant)

    assert tenant.id is not None
    assert tenant.slug == "juice-island"
    assert tenant.is_verified is False
    assert tenant.is_live is False


# ── Menu models ───────────────────────────────────────────────────────────────
def test_create_category_and_product(session):
    from app.models import Tenant, Category, Product

    tenant = Tenant(
        slug="test-cafe",
        business_name="Test Cafe",
        owner_email="cafe@test.com",
        hashed_password="x",
        currency="USD",
    )
    session.add(tenant)
    session.commit()
    session.refresh(tenant)

    category = Category(tenant_id=tenant.id, name="Fresh Juices", display_order=1)
    session.add(category)
    session.commit()
    session.refresh(category)

    product = Product(
        tenant_id=tenant.id,
        category_id=category.id,
        name="Mango Madness",
        price=4.99,
        is_best_seller=True,
    )
    session.add(product)
    session.commit()
    session.refresh(product)

    assert product.id is not None
    assert product.price == 4.99
    assert product.is_best_seller is True


# ── Cart session ──────────────────────────────────────────────────────────────
def test_cart_session_json_helpers(session):
    from app.models import Tenant, CartSession

    tenant = Tenant(
        slug="cart-test",
        business_name="Cart Test",
        owner_email="cart@test.com",
        hashed_password="x",
        currency="USD",
    )
    session.add(tenant)
    session.commit()
    session.refresh(tenant)

    cart = CartSession(tenant_id=tenant.id, customer_phone="+923001234567")
    cart.set_cart([{"product_id": 1, "name": "Mango Madness", "qty": 2, "unit_price": 4.99}])
    session.add(cart)
    session.commit()
    session.refresh(cart)

    items = cart.get_cart()
    assert len(items) == 1
    assert items[0]["qty"] == 2
    assert items[0]["unit_price"] == 4.99


# ── Security helpers ──────────────────────────────────────────────────────────
def test_password_hashing():
    from app.core.security import hash_password, verify_password
    hashed = hash_password("MySecret123")
    assert hashed != "MySecret123"
    assert verify_password("MySecret123", hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_jwt_token_encode_decode():
    from app.core.security import create_access_token, decode_access_token
    token = create_access_token({"sub": "owner@juiceisland.com", "tenant_id": 1})
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "owner@juiceisland.com"
    assert payload["tenant_id"] == 1


def test_jwt_invalid_token():
    from app.core.security import decode_access_token
    result = decode_access_token("this.is.not.valid")
    assert result is None


def test_generate_verify_token():
    from app.core.security import generate_verify_token
    token = generate_verify_token()
    assert len(token) > 20
    assert token != generate_verify_token()   # each call unique
