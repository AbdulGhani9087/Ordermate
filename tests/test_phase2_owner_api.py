import io
from app.models.order import Order, OrderItem, OrderStatus, OrderType


def test_register_and_login(client):
    # 1. Register Juice Island
    reg_payload = {
        "business_name": "Juice Island",
        "owner_email": "owner@juiceisland.com",
        "password": "Password123!",
        "contact_phone": "+1234567890",
        "business_category": "Fresh Juices & Smoothies",
        "currency": "USD",
    }
    r = client.post("/api/v1/auth/register", json=reg_payload)
    assert r.status_code == 201
    data = r.json()
    assert "access_token" in data
    assert data["slug"] == "juice-island"
    token = data["access_token"]

    # 2. Duplicate registration fails
    r_dup = client.post("/api/v1/auth/register", json=reg_payload)
    assert r_dup.status_code == 400

    # 3. Login
    login_payload = {"email": "owner@juiceisland.com", "password": "Password123!"}
    r_login = client.post("/api/v1/auth/login", json=login_payload)
    assert r_login.status_code == 200
    assert "access_token" in r_login.json()

    # 4. Auth Me
    headers = {"Authorization": f"Bearer {token}"}
    r_me = client.get("/api/v1/auth/me", headers=headers)
    assert r_me.status_code == 200
    assert r_me.json()["business_name"] == "Juice Island"


def test_store_settings_and_whatsapp_config(client):
    # Register
    r = client.post("/api/v1/auth/register", json={
        "business_name": "Tropical Sips",
        "owner_email": "sips@tropical.com",
        "password": "Password123!",
    })
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Update store settings
    settings_payload = {
        "delivery_enabled": True,
        "pickup_enabled": True,
        "delivery_fee": 2.50,
        "min_order_value": 10.0,
    }
    r_set = client.put("/api/v1/tenants/settings", json=settings_payload, headers=headers)
    assert r_set.status_code == 200
    assert r_set.json()["delivery_fee"] == 2.50

    # Save WhatsApp Cloud API config
    wa_payload = {
        "phone_number_id": "100987654321",
        "waba_id": "9988776655",
        "access_token": "EAAX...dummy_token",
    }
    r_wa = client.post("/api/v1/tenants/whatsapp-config", json=wa_payload, headers=headers)
    assert r_wa.status_code == 200
    assert r_wa.json()["phone_number_id"] == "100987654321"
    assert r_wa.json()["is_connected"] is True


def test_menu_crud_and_csv_upload(client):
    # Register
    r = client.post("/api/v1/auth/register", json={
        "business_name": "Smoothie Land",
        "owner_email": "land@smoothie.com",
        "password": "Password123!",
    })
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create Category
    r_cat = client.post("/api/v1/menu/categories", json={"name": "Fresh Juices", "display_order": 1}, headers=headers)
    assert r_cat.status_code == 201
    cat_id = r_cat.json()["id"]

    # 2. Create Product
    prod_payload = {
        "category_id": cat_id,
        "name": "Mango Madness",
        "description": "Sweet Pakistani mangoes blended fresh",
        "price": 4.99,
        "is_best_seller": True,
    }
    r_prod = client.post("/api/v1/menu/items", json=prod_payload, headers=headers)
    assert r_prod.status_code == 201
    assert r_prod.json()["is_best_seller"] is True

    # 3. CSV Bulk Upload
    csv_content = """category,name,price,description,is_best_seller,image_url
Fresh Juices,Orange Sunshine,4.49,Cold pressed fresh oranges,false,
Smoothies,Avocado Power,5.99,Avocado honey and milk,true,
Smoothies,Berry Blast,5.49,Mixed strawberries and blueberries,false,
"""
    csv_file = io.BytesIO(csv_content.encode("utf-8"))
    files = {"file": ("menu.csv", csv_file, "text/csv")}
    r_csv = client.post("/api/v1/menu/upload-csv", files=files, headers=headers)
    assert r_csv.status_code == 200
    res = r_csv.json()
    assert res["imported"] == 3
    assert res["skipped"] == 0

    # 4. Check full menu
    r_menu = client.get("/api/v1/menu", headers=headers)
    assert r_menu.status_code == 200
    menu = r_menu.json()
    total_items = sum(len(c["products"]) for c in menu["categories"]) + len(menu["uncategorized"])
    assert total_items == 4


def test_orders_management(client, session):
    # Register
    r = client.post("/api/v1/auth/register", json={
        "business_name": "Order Test Cafe",
        "owner_email": "orders@cafe.com",
        "password": "Password123!",
    })
    token = r.json()["access_token"]
    tenant_id = r.json()["tenant_id"]
    headers = {"Authorization": f"Bearer {token}"}

    # Insert a sample order directly into DB
    order = Order(
        order_number="OM-1001",
        tenant_id=tenant_id,
        customer_phone="+923001234567",
        customer_name="Ali Khan",
        order_type=OrderType.delivery,
        delivery_address="Street 10, House 42",
        status=OrderStatus.pending,
        subtotal=10.98,
        delivery_fee=2.00,
        total=12.98,
    )
    session.add(order)
    session.commit()
    session.refresh(order)

    item1 = OrderItem(order_id=order.id, product_name="Mango Madness", unit_price=4.99, quantity=2, subtotal=9.98)
    session.add(item1)
    session.commit()
    order_id = order.id

    # 1. Fetch orders via API
    r_orders = client.get("/api/v1/orders", headers=headers)
    assert r_orders.status_code == 200
    orders_list = r_orders.json()
    assert len(orders_list) == 1
    assert orders_list[0]["order_number"] == "OM-1001"
    assert orders_list[0]["items"][0]["product_name"] == "Mango Madness"

    # 2. Update status to "preparing"
    r_update = client.patch(f"/api/v1/orders/{order_id}/status", json={"status": "preparing"}, headers=headers)
    assert r_update.status_code == 200
    assert r_update.json()["status"] == "preparing"
