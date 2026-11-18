from sqlmodel import select
from app.models.tenant import Tenant, StoreSettings, WhatsAppConfig, StoreHours
from app.models.menu import Category, Product
from app.models.order import Order, OrderStatus, OrderType


def seed_juice_island_tenant(session):
    tenant = Tenant(
        slug="juice-island",
        business_name="Juice Island",
        owner_email="owner@juiceisland.com",
        hashed_password="hashedpassword",
        currency="USD",
        is_active=True,
        is_live=True,
    )
    session.add(tenant)
    session.commit()
    session.refresh(tenant)

    settings = StoreSettings(
        tenant_id=tenant.id,
        delivery_enabled=True,
        pickup_enabled=True,
        delivery_fee=2.00,
        delivery_eta_mins=30,
        pickup_eta_mins=15,
    )
    session.add(settings)

    config = WhatsAppConfig(
        tenant_id=tenant.id,
        verify_token="JUICE_ISLAND_SECRET_TOKEN",
        webhook_url=f"/api/v1/webhook/{tenant.slug}",
        phone_number_id="10101010",
        access_token="EAAX...dummy",
        is_connected=True,
    )
    session.add(config)

    # Store hours: 00:00 to 23:59 everyday
    for day in range(7):
        session.add(StoreHours(
            tenant_id=tenant.id,
            weekday=day,
            open_time="00:00",
            close_time="23:59",
            is_closed=False,
        ))

    # Categories
    cat_juices = Category(tenant_id=tenant.id, name="Fresh Juices", display_order=1)
    cat_shakes = Category(tenant_id=tenant.id, name="Power Shakes", display_order=2)
    session.add(cat_juices)
    session.add(cat_shakes)
    session.commit()
    session.refresh(cat_juices)
    session.refresh(cat_shakes)

    # Products
    p1 = Product(
        tenant_id=tenant.id,
        category_id=cat_juices.id,
        name="Mango Madness",
        description="Pure ripe mangoes with crushed ice",
        price=4.99,
        is_available=True,
        is_best_seller=True,
    )
    p2 = Product(
        tenant_id=tenant.id,
        category_id=cat_juices.id,
        name="Orange Sunshine",
        description="Freshly squeezed Valencia oranges",
        price=3.99,
        is_available=True,
        is_best_seller=False,
    )
    p3 = Product(
        tenant_id=tenant.id,
        category_id=cat_shakes.id,
        name="Avocado Power",
        description="Fresh avocado with honey and almond milk",
        price=5.99,
        is_available=True,
        is_best_seller=True,
    )
    session.add(p1)
    session.add(p2)
    session.add(p3)
    session.commit()

    return tenant.id


def test_meta_webhook_verification(client, session):
    seed_juice_island_tenant(session)

    # Valid verification challenge from Meta
    r = client.get("/api/v1/webhook/juice-island", params={
        "hub.mode": "subscribe",
        "hub.challenge": "987654321",
        "hub.verify_token": "JUICE_ISLAND_SECRET_TOKEN",
    })
    assert r.status_code == 200
    assert r.text == "987654321"

    # Invalid token rejected
    r_bad = client.get("/api/v1/webhook/juice-island", params={
        "hub.mode": "subscribe",
        "hub.challenge": "987654321",
        "hub.verify_token": "WRONG_TOKEN",
    })
    assert r_bad.status_code == 403


def test_end_to_end_customer_ordering_journey_simulator(client, session):
    tenant_id = seed_juice_island_tenant(session)
    phone = "+923009988776"

    # 1. Customer greets
    r1 = client.post("/api/v1/simulator/juice-island/chat", json={
        "customer_phone": phone,
        "message": "Hi",
    })
    assert r1.status_code == 200
    assert "Juice Island" in r1.json()["reply_text"]

    # 2. Customer asks for menu
    r2 = client.post("/api/v1/simulator/juice-island/chat", json={
        "customer_phone": phone,
        "message": "Show menu",
    })
    assert r2.status_code == 200
    text2 = r2.json()["reply_text"]
    assert "FRESH JUICES" in text2
    assert "Mango Madness" in text2
    assert "Orange Sunshine" in text2

    # 3. Customer asks for recommendation
    r3 = client.post("/api/v1/simulator/juice-island/chat", json={
        "customer_phone": phone,
        "message": "What is your best juice?",
    })
    assert r3.status_code == 200
    assert "Mango Madness" in r3.json()["reply_text"]

    # 4. Customer adds items to cart
    # 2x Mango Madness (2 * 4.99 = 9.98) and 1x Avocado Power (5.99) => Subtotal = 15.97
    r4 = client.post("/api/v1/simulator/juice-island/chat", json={
        "customer_phone": phone,
        "message": "I want 2 Mango Madness and 1 Avocado Power",
    })
    assert r4.status_code == 200
    text4 = r4.json()["reply_text"]
    assert "Added" in text4
    assert "15.97" in text4

    # 5. Customer initiates checkout
    r5 = client.post("/api/v1/simulator/juice-island/chat", json={
        "customer_phone": phone,
        "message": "Checkout",
    })
    assert r5.status_code == 200
    assert "receive your order" in r5.json()["reply_text"]

    # 6. Customer chooses Delivery
    r6 = client.post("/api/v1/simulator/juice-island/chat", json={
        "customer_phone": phone,
        "message": "Delivery",
    })
    assert r6.status_code == 200
    assert "Delivery selected" in r6.json()["reply_text"]

    # 7. Customer enters delivery address
    r7 = client.post("/api/v1/simulator/juice-island/chat", json={
        "customer_phone": phone,
        "message": "Tariq Road, House 88, Karachi",
    })
    assert r7.status_code == 200
    text7 = r7.json()["reply_text"]
    assert "Tariq Road" in text7
    # Subtotal 15.97 + Delivery Fee 2.00 = 17.97
    assert "17.97" in text7

    # 8. Customer confirms order
    r8 = client.post("/api/v1/simulator/juice-island/chat", json={
        "customer_phone": phone,
        "message": "CONFIRM",
    })
    assert r8.status_code == 200
    data8 = r8.json()
    assert "ORDER CONFIRMED" in data8["reply_text"]
    assert data8["order_id"] is not None
    assert "OM-" in data8["order_number"]

    # 9. Verify order is registered in database with correct tenant, items, and total
    orders = session.exec(select(Order).where(Order.tenant_id == tenant_id)).all()
    assert len(orders) == 1
    db_order = orders[0]
    assert db_order.customer_phone == phone
    assert db_order.order_type == OrderType.delivery
    assert db_order.status == OrderStatus.pending
    assert db_order.delivery_fee == 2.00
    assert round(db_order.subtotal, 2) == 15.97
    assert round(db_order.total, 2) == 17.97
    assert db_order.delivery_address == "Tariq Road, House 88, Karachi"


def test_meta_webhook_incoming_message_payload(client, session):
    seed_juice_island_tenant(session)

    meta_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123456789",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15551234567",
                                "phone_number_id": "10101010",
                            },
                            "messages": [
                                {
                                    "from": "923001122334",
                                    "id": "wamid.HBgLM...",
                                    "timestamp": "1731945000",
                                    "text": {"body": "Hi"},
                                    "type": "text",
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }

    r = client.post("/api/v1/webhook/juice-island", json=meta_payload)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "Juice Island" in data["response"]["reply_text"]
