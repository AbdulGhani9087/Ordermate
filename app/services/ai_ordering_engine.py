import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from sqlmodel import Session, select

from app.models.tenant import Tenant, StoreSettings, StoreHours
from app.models.menu import Category, Product
from app.models.order import Order, OrderItem, CartSession, OrderStatus, OrderType


class AIOrderingEngine:
    """
    Intelligent conversational ordering engine.
    State machine steps:
      - IDLE: General conversation, greeting, menu display, recommendations.
      - CART_ACTIVE: Customer has items in cart, can add more, view cart, or checkout.
      - AWAITING_FULFILLMENT: Choose Delivery vs Pickup.
      - AWAITING_ADDRESS: Enter delivery address & name.
      - AWAITING_CONFIRMATION: Confirm order.
    """

    @classmethod
    def get_or_create_session(cls, tenant_id: int, customer_phone: str, db: Session) -> CartSession:
        cart_sess = db.exec(
            select(CartSession)
            .where(CartSession.tenant_id == tenant_id)
            .where(CartSession.customer_phone == customer_phone)
        ).first()

        if not cart_sess:
            cart_sess = CartSession(
                tenant_id=tenant_id,
                customer_phone=customer_phone,
                state_step="IDLE",
                cart_items="[]",
            )
            db.add(cart_sess)
            db.commit()
            db.refresh(cart_sess)
        return cart_sess

    @classmethod
    def check_store_open(cls, tenant_id: int, db: Session) -> Tuple[bool, str]:
        """Checks if the store is currently open based on StoreHours."""
        now = datetime.now()
        current_weekday = now.weekday()  # 0=Monday, 6=Sunday
        current_time_str = now.strftime("%H:%M")

        store_hour = db.exec(
            select(StoreHours)
            .where(StoreHours.tenant_id == tenant_id)
            .where(StoreHours.weekday == current_weekday)
        ).first()

        if not store_hour or store_hour.is_closed:
            return False, "We are closed today. Please check back during our regular hours!"

        if store_hour.open_time and store_hour.close_time:
            if not (store_hour.open_time <= current_time_str <= store_hour.close_time):
                return False, f"We are currently closed. Today's hours are {store_hour.open_time} to {store_hour.close_time}."

        return True, ""

    @classmethod
    def format_menu(cls, tenant: Tenant, db: Session) -> str:
        categories = db.exec(
            select(Category)
            .where(Category.tenant_id == tenant.id)
            .where(Category.is_active == True)
            .order_by(Category.display_order, Category.name)
        ).all()

        lines = [f"🍹 *Welcome to {tenant.business_name}!* 🍹", "Here is our fresh menu:\n"]

        curr = tenant.currency or "USD"

        for cat in categories:
            products = db.exec(
                select(Product)
                .where(Product.tenant_id == tenant.id)
                .where(Product.category_id == cat.id)
                .where(Product.is_available == True)
            ).all()
            if products:
                lines.append(f"✨ *{cat.name.upper()}*")
                for p in products:
                    star = " ⭐ (Best Seller)" if p.is_best_seller else ""
                    lines.append(f" • *{p.name}* — {curr} {p.price:.2f}{star}")
                    if p.description:
                        lines.append(f"   _{p.description}_")
                lines.append("")

        # Uncategorized
        uncat = db.exec(
            select(Product)
            .where(Product.tenant_id == tenant.id)
            .where(Product.category_id == None)
            .where(Product.is_available == True)
        ).all()
        if uncat:
            lines.append("✨ *OTHER ITEMS*")
            for p in uncat:
                star = " ⭐ (Best Seller)" if p.is_best_seller else ""
                lines.append(f" • *{p.name}* — {curr} {p.price:.2f}{star}")
            lines.append("")

        lines.append("👉 Reply with what you'd like to order (e.g. *'2 Mango Madness'*) or ask *'What is your best juice?'*")
        return "\n".join(lines)

    @classmethod
    def format_recommendations(cls, tenant: Tenant, db: Session) -> str:
        curr = tenant.currency or "USD"
        best_sellers = db.exec(
            select(Product)
            .where(Product.tenant_id == tenant.id)
            .where(Product.is_available == True)
            .where(Product.is_best_seller == True)
        ).all()

        if not best_sellers:
            best_sellers = db.exec(
                select(Product)
                .where(Product.tenant_id == tenant.id)
                .where(Product.is_available == True)
                .limit(3)
            ).all()

        if not best_sellers:
            return f"Welcome to {tenant.business_name}! Our menu is currently being refreshed."

        lines = [
            f"🌟 *Top Recommendations from {tenant.business_name}* 🌟\n",
            "Our customers love these favorites:",
        ]
        for p in best_sellers:
            lines.append(f"• *{p.name}* — {curr} {p.price:.2f}")
            if p.description:
                lines.append(f"  _{p.description}_")

        lines.append("\nWould you like to try one of these? Reply e.g. *'1 " + best_sellers[0].name + "'* to start your order!")
        return "\n".join(lines)

    @classmethod
    def format_cart(cls, cart_items: List[Dict], tenant: Tenant, settings: Optional[StoreSettings] = None, order_type: Optional[str] = None) -> str:
        curr = tenant.currency or "USD"
        if not cart_items:
            return "🛒 Your cart is currently empty! Reply with an item from our menu to add it."

        lines = ["🛒 *Your Cart:*"]
        subtotal = 0.0
        for it in cart_items:
            item_tot = it["qty"] * it["unit_price"]
            subtotal += item_tot
            lines.append(f" • {it['qty']}x *{it['name']}* — {curr} {item_tot:.2f}")

        lines.append(f"\n*Subtotal:* {curr} {subtotal:.2f}")

        delivery_fee = 0.0
        if order_type == "delivery" and settings and settings.delivery_fee:
            delivery_fee = settings.delivery_fee
            lines.append(f"*Delivery Fee:* {curr} {delivery_fee:.2f}")
            lines.append(f"*Total:* {curr} {(subtotal + delivery_fee):.2f}")
        else:
            lines.append(f"*Estimated Total:* {curr} {subtotal:.2f}")

        return "\n".join(lines)

    @classmethod
    def find_matching_products(cls, text: str, tenant_id: int, db: Session) -> List[tuple]:
        """
        Parses text for quantities and product names.
        Returns list of (Product, qty).
        """
        available_products = db.exec(
            select(Product)
            .where(Product.tenant_id == tenant_id)
            .where(Product.is_available == True)
        ).all()

        matches = []
        cleaned_text = text.lower()

        for p in available_products:
            p_name_lower = p.name.lower()
            # Check for direct phrase match or key words
            pattern = rf"(\d+)?\s*(?:x\s*)?{re.escape(p_name_lower)}"
            match = re.search(pattern, cleaned_text)
            if match:
                qty_str = match.group(1)
                qty = int(qty_str) if qty_str else 1
                matches.append((p, qty))
            elif any(part in cleaned_text for part in p_name_lower.split() if len(part) > 3):
                # Substring match (e.g. "mango" in "Mango Madness")
                # Look for preceding digits
                qty_match = re.search(r"(\d+)\s*(?:x\s*)?[a-z\s]*" + re.escape(p_name_lower.split()[0]), cleaned_text)
                qty = int(qty_match.group(1)) if qty_match else 1
                # Avoid duplicates
                if not any(m[0].id == p.id for m in matches):
                    matches.append((p, qty))

        return matches

    @classmethod
    def process_message(
        cls,
        tenant: Tenant,
        customer_phone: str,
        message_text: str,
        db: Session,
    ) -> Dict[str, Any]:
        """
        Main conversational entry point.
        Returns dict with:
          - reply_text: str
          - buttons: Optional[List[Dict[str, str]]]
          - order_id: Optional[int]
        """
        raw = message_text.strip()
        text_lower = raw.lower()

        cart_session = cls.get_or_create_session(tenant.id, customer_phone, db)
        settings = db.exec(select(StoreSettings).where(StoreSettings.tenant_id == tenant.id)).first()
        if not settings:
            settings = StoreSettings(tenant_id=tenant.id)

        # ── 1. Clear / Reset / Cancel ─────────────────────────────────────────
        if text_lower in ("cancel", "clear", "reset", "start over", "khatam"):
            cart_session.state_step = "IDLE"
            cart_session.set_cart([])
            cart_session.selected_type = None
            cart_session.delivery_address = None
            db.add(cart_session)
            db.commit()
            return {
                "reply_text": f"Your order has been reset. 🍹\n\nHow can {tenant.business_name} help you today? Reply *'menu'* to view items.",
                "buttons": None,
            }

        # ── 2. Greeting & Help ────────────────────────────────────────────────
        if text_lower in ("hi", "hello", "hey", "salam", "assalam o alaikum", "start"):
            return {
                "reply_text": (
                    f"Hello! Welcome to *{tenant.business_name}* 🥭🍹\n\n"
                    "I am your AI Ordering Assistant. Here is how I can help:\n"
                    "• Reply *'menu'* to see our fresh products & prices\n"
                    "• Ask *'what is your best juice?'* for recommendations\n"
                    "• Or simply tell me what you want: e.g. *'2 Mango Madness and 1 Avocado Power'*"
                ),
                "buttons": [
                    {"id": "view_menu", "title": "📜 View Menu"},
                    {"id": "recommendations", "title": "⭐ Best Sellers"},
                ],
            }

        # ── 3. Recommendations Intent ────────────────────────────────────────
        if any(kw in text_lower for kw in ("best", "recommend", "special", "kya acha", "favorite", "favourite", "mashhoor")):
            return {
                "reply_text": cls.format_recommendations(tenant, db),
                "buttons": [
                    {"id": "view_menu", "title": "📜 Full Menu"},
                ],
            }

        # ── 4. Menu Intent ───────────────────────────────────────────────────
        if any(kw in text_lower for kw in ("menu", "list", "items", "dikhao", "kya hai", "prices", "options")):
            return {
                "reply_text": cls.format_menu(tenant, db),
                "buttons": [
                    {"id": "recommendations", "title": "⭐ Best Sellers"},
                ],
            }

        # ── 5. View Cart ─────────────────────────────────────────────────────
        if text_lower in ("cart", "show cart", "my cart", "basket", "mera cart"):
            cart = cart_session.get_cart()
            if not cart:
                return {
                    "reply_text": "Your cart is empty! 🛒\nReply with an item like *'1 Mango Madness'* to begin.",
                    "buttons": [{"id": "view_menu", "title": "📜 View Menu"}],
                }
            cart_str = cls.format_cart(cart, tenant, settings, cart_session.selected_type)
            return {
                "reply_text": f"{cart_str}\n\n👉 Reply *'checkout'* to place your order or add more items!",
                "buttons": [
                    {"id": "checkout", "title": "🛍️ Checkout"},
                    {"id": "clear", "title": "❌ Clear Cart"},
                ],
            }

        # ── 6. Fulfillment Selection (Delivery vs Pickup) ────────────────────
        if cart_session.state_step == "AWAITING_FULFILLMENT" or text_lower in ("delivery", "pickup"):
            cart = cart_session.get_cart()
            if not cart:
                return {
                    "reply_text": "Your cart is empty! Please select some items from the menu first.",
                    "buttons": [{"id": "view_menu", "title": "📜 View Menu"}],
                }

            if "deliver" in text_lower:
                cart_session.selected_type = "delivery"
                cart_session.state_step = "AWAITING_ADDRESS"
                db.add(cart_session)
                db.commit()
                return {
                    "reply_text": (
                        "🛵 *Delivery selected!*\n\n"
                        f"Delivery Fee: {tenant.currency} {settings.delivery_fee:.2f}\n"
                        "Please provide your *Delivery Address* and *Name*:\n"
                        "_(e.g. 'Ali Khan, House 12, Street 4, Sector G-10')_"
                    ),
                    "buttons": None,
                }
            elif "pickup" in text_lower:
                cart_session.selected_type = "pickup"
                cart_session.state_step = "AWAITING_CONFIRMATION"
                db.add(cart_session)
                db.commit()
                cart_str = cls.format_cart(cart, tenant, settings, order_type="pickup")
                return {
                    "reply_text": (
                        f"🏪 *Pickup selected!*\nReady in approx ~{settings.pickup_eta_mins} mins.\n\n"
                        f"{cart_str}\n\n"
                        "Reply *'CONFIRM'* to finalize your pickup order! ✅"
                    ),
                    "buttons": [{"id": "confirm", "title": "✅ Confirm Order"}],
                }

        # ── 7. Address Entry (when in AWAITING_ADDRESS) ───────────────────────
        if cart_session.state_step == "AWAITING_ADDRESS":
            cart = cart_session.get_cart()
            cart_session.delivery_address = raw
            cart_session.state_step = "AWAITING_CONFIRMATION"
            db.add(cart_session)
            db.commit()

            cart_str = cls.format_cart(cart, tenant, settings, order_type="delivery")
            return {
                "reply_text": (
                    f"📍 *Delivery to:* {raw}\n\n"
                    f"{cart_str}\n\n"
                    "Reply *'CONFIRM'* or tap the button to place your order! 🚀"
                ),
                "buttons": [
                    {"id": "confirm", "title": "✅ Confirm Order"},
                    {"id": "cancel", "title": "❌ Cancel"},
                ],
            }

        # ── 8. Checkout Intent ────────────────────────────────────────────────
        if text_lower in ("checkout", "order now", "done", "order kar do", "place order"):
            cart = cart_session.get_cart()
            if not cart:
                return {
                    "reply_text": "Your cart is currently empty! Reply with an item from our menu to start.",
                    "buttons": [{"id": "view_menu", "title": "📜 View Menu"}],
                }

            # Check operating hours
            is_open, closed_msg = cls.check_store_open(tenant.id, db)
            if not is_open:
                return {"reply_text": f"⏳ {closed_msg}", "buttons": None}

            cart_session.state_step = "AWAITING_FULFILLMENT"
            db.add(cart_session)
            db.commit()

            cart_str = cls.format_cart(cart, tenant, settings)
            buttons = []
            if settings.delivery_enabled:
                buttons.append({"id": "delivery", "title": "🛵 Delivery"})
            if settings.pickup_enabled:
                buttons.append({"id": "pickup", "title": "🏪 Pickup"})

            return {
                "reply_text": (
                    f"{cart_str}\n\n"
                    "How would you like to receive your order?"
                ),
                "buttons": buttons or None,
            }

        # ── 9. Final Confirmation ─────────────────────────────────────────────
        if cart_session.state_step == "AWAITING_CONFIRMATION" and text_lower in ("confirm", "yes", "ha", "haan", "theek hai", "ok"):
            cart = cart_session.get_cart()
            if not cart:
                return {"reply_text": "No active items in cart to confirm.", "buttons": None}

            subtotal = sum(it["qty"] * it["unit_price"] for it in cart)
            delivery_fee = settings.delivery_fee if cart_session.selected_type == "delivery" else 0.0
            total = subtotal + delivery_fee

            # Create Order in DB
            order = Order(
                order_number="OM-TEMP",
                tenant_id=tenant.id,
                customer_phone=customer_phone,
                customer_name=cart_session.customer_name or "WhatsApp Customer",
                order_type=OrderType.delivery if cart_session.selected_type == "delivery" else OrderType.pickup,
                delivery_address=cart_session.delivery_address,
                status=OrderStatus.pending,
                subtotal=subtotal,
                delivery_fee=delivery_fee,
                total=total,
                payment_method="cash_on_delivery",
            )
            db.add(order)
            db.commit()
            db.refresh(order)

            # Assign human readable order number e.g. OM-1042
            order.order_number = f"OM-{1000 + order.id}"
            db.add(order)

            # Create OrderItems
            for it in cart:
                order_item = OrderItem(
                    order_id=order.id,
                    product_id=it.get("product_id"),
                    product_name=it["name"],
                    unit_price=it["unit_price"],
                    quantity=it["qty"],
                    subtotal=it["qty"] * it["unit_price"],
                )
                db.add(order_item)

            # Reset cart session
            cart_session.state_step = "IDLE"
            cart_session.set_cart([])
            cart_session.selected_type = None
            cart_session.delivery_address = None
            db.add(cart_session)
            db.commit()

            curr = tenant.currency or "USD"
            fulfillment_line = f"🛵 Delivery to: {order.delivery_address}" if order.order_type == OrderType.delivery else f"🏪 Self-Pickup (Ready in ~{settings.pickup_eta_mins} mins)"

            return {
                "reply_text": (
                    f"🎉 *ORDER CONFIRMED!*\n\n"
                    f"*Order ID:* #{order.order_number}\n"
                    f"*Store:* {tenant.business_name}\n"
                    f"*{fulfillment_line}*\n"
                    f"*Total Amount:* {curr} {order.total:.2f} (Cash on Delivery)\n\n"
                    f"We have notified {tenant.business_name} and your fresh order is being prepared! 🥭🍹\n"
                    "Thank you for ordering with us!"
                ),
                "buttons": None,
                "order_id": order.id,
                "order_number": order.order_number,
            }

        # ── 10. Item matching / Add to Cart ───────────────────────────────────
        matched_items = cls.find_matching_products(raw, tenant.id, db)
        if matched_items:
            cart = cart_session.get_cart()
            added_descriptions = []

            for product, qty in matched_items:
                # Check if item already exists in cart
                existing = next((it for it in cart if it.get("product_id") == product.id), None)
                if existing:
                    existing["qty"] += qty
                else:
                    cart.append({
                        "product_id": product.id,
                        "name": product.name,
                        "unit_price": product.price,
                        "qty": qty,
                    })
                added_descriptions.append(f"{qty}x {product.name}")

            cart_session.set_cart(cart)
            cart_session.state_step = "CART_ACTIVE"
            db.add(cart_session)
            db.commit()

            cart_str = cls.format_cart(cart, tenant, settings)
            added_txt = ", ".join(added_descriptions)

            return {
                "reply_text": (
                    f"✅ Added *{added_txt}* to your cart!\n\n"
                    f"{cart_str}\n\n"
                    "Reply with more items, or type *'checkout'* to place your order! 🛍️"
                ),
                "buttons": [
                    {"id": "checkout", "title": "🛍️ Checkout"},
                    {"id": "view_menu", "title": "📜 Menu"},
                ],
            }

        # ── 11. Fallback ─────────────────────────────────────────────────────
        return {
            "reply_text": (
                f"Sorry, I didn't quite catch that. 😊\n\n"
                f"You can:\n"
                f"• Reply *'menu'* to view what {tenant.business_name} offers\n"
                f"• Reply *'best'* to see our customer favorites\n"
                f"• Or type an item name like *'1 Mango Madness'*"
            ),
            "buttons": [
                {"id": "view_menu", "title": "📜 View Menu"},
                {"id": "recommendations", "title": "⭐ Best Sellers"},
            ],
        }
