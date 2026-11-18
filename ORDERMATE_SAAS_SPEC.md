# OrderMate AI — Self-Service Multi-Tenant WhatsApp Ordering SaaS

## Overview
OrderMate AI is a **multi-tenant, self-service SaaS platform** designed for local and physical businesses (such as juice bars, cafes, takeaway restaurants, and bakeries).

Because business owners often cannot or prefer not to share their private credentials (Meta logins, WhatsApp API keys, server accesses) directly with third parties, OrderMate AI operates as a **100% Self-Service Portal**.

Owners create an account, enter their own store details and Meta WhatsApp credentials, upload or build their menu (manually, via CSV, or by uploading a menu photo), test the AI in an interactive sandbox, and manage orders in real time — all without involving a developer.

---

## 1. What We Currently Have (Current State)

| Component | Status | Details |
| :--- | :--- | :--- |
| **Project Setup** | ✅ Done | Python 3.12, FastAPI, SQLite engine initialized in `app/db/database.py` |
| **Core Structure** | ✅ Done | Directories created: `models/`, `api/routes/`, `schemas/`, `core/`, `services/` |
| **Base App** | ✅ Running | Minimal FastAPI entry in `app/main.py` with `/` and `/health` endpoints |
| **Dependencies** | 🔄 Partial | `requirements.txt` has FastAPI, SQLModel, Uvicorn, Pytest — still needs: `passlib[bcrypt]`, `python-jose`, `python-multipart`, `Pillow`, `google-generativeai`, `jinja2`, `aiofiles` |

---

## 2. Target System Architecture

```
                       ┌──────────────────────────────────┐
                       │      WhatsApp Cloud API           │
                       │          (Meta Graph API)         │
                       └──────────────┬───────────────▲───┘
                                      │ Incoming Msg   │ Send Msg
                                      ▼               │
┌────────────────────────────────────────────────────────────────────────────┐
│                              OrderMate AI SaaS                             │
│                                                                            │
│  ┌─────────────────────────────┐      ┌──────────────────────────────────┐ │
│  │   Business Owner Portal     │      │   WhatsApp Ordering Engine       │ │
│  │                             │      │                                  │ │
│  │  • Register & Email Verify  │      │  • Webhook Receiver & Validator  │ │
│  │  • Business Profile Setup   │      │  • Multilingual NLP + Intent     │ │
│  │  • Meta WhatsApp Config     │      │  • Menu Search (per Tenant)      │ │
│  │  • Menu Builder             │      │  • Recommendations Engine        │ │
│  │    - Manual Entry           │      │  • Cart State Machine (DB-backed)│ │
│  │    - CSV Bulk Upload        │      │  • Delivery / Pickup Checkout    │ │
│  │    - Menu Image/PDF AI OCR  │      │  • Store Hours Validation        │ │
│  │  • Product Image Upload     │      │  • Closed-Store / Out-of-Stock   │ │
│  │  • Store Hours & Delivery   │      │    Error Handling                │ │
│  │  • AI Chat Simulator        │      │  • Order Confirmation & ID Gen   │ │
│  │  • Live Orders Dashboard    │◄─────│  • Owner Notification Trigger    │ │
│  │  • Owner WhatsApp Alerts    │      │                                  │ │
│  └────────────┬────────────────┘      └──────────────────┬───────────────┘ │
│               │                                          │                 │
│               └────────────────────┬─────────────────────┘                 │
│                                    ▼                                       │
│                       ┌────────────────────────┐                           │
│                       │  SQLite (Dev)           │                           │
│                       │  PostgreSQL (Production)│                           │
│                       │  Multi-Tenant Database  │                           │
│                       └────────────────────────┘                           │
│                                                                            │
│                       ┌────────────────────────┐                           │
│                       │  File Storage           │                           │
│                       │  /static/uploads/       │                           │
│                       │  {tenant_id}/products/  │                           │
│                       └────────────────────────┘                           │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. The Two Core Journeys

### Journey A: Business Owner (Self-Service, 9 Steps)

1. **Visit OrderMate AI website**: Lands on the homepage explaining how WhatsApp order automation works.
2. **Create account & verify email**: Owner signs up with business email and password. A verification email is sent; unverified accounts cannot go live.
3. **Create business profile**: Enters business name, slug (used in webhook URL), category (e.g. *Juice Bar & Shakes*), country, currency, and contact phone.
4. **Connect WhatsApp through Meta**: Self-service input of:
   - Meta Phone Number ID
   - WhatsApp Business Account ID (WABA ID)
   - Permanent System User Access Token
   - System generates a unique **Webhook URL** (`https://ordermate.ai/webhook/{tenant_slug}`) and a **Verify Token** to paste into Meta Developer Dashboard.
5. **Upload or enter menu** *(3 options, can mix and match)*:
   - **Option A — Manual Entry**: Enter Category, Item Name, Price, Description, Size variants, Availability toggle, and upload item photo.
   - **Option B — CSV Bulk Upload**: Upload a `.csv` file. Required columns:
     ```
     category | name | price | description | is_best_seller | image_url
     ```
     Example:
     ```csv
     category,name,price,description,is_best_seller,image_url
     Fresh Juices,Mango Madness,4.99,Fresh mango blended with ice,true,
     Fresh Juices,Orange Sunshine,4.49,Cold-pressed navel oranges,false,
     Shakes,Avocado Power Shake,5.99,Creamy avocado and honey,true,
     ```
     - `image_url` is optional. Leave blank if uploading photos separately.
     - System skips rows with missing `name` or `price` and reports them back.
   - **Option C — AI Menu Extractor**: Upload a photo or PDF of a printed/handwritten menu. AI (Google Gemini Vision) reads the image and extracts categories, items, prices, and descriptions into a draft table for review.
6. **Review extracted products and prices**: After CSV or AI extraction, the owner sees an editable table. They can fix prices, rename items, toggle availability, and add photos before saving.
7. **Configure delivery, pickup, and opening hours**:
   - Opening and closing times per weekday (Mon–Sun), with ability to mark days as closed.
   - Delivery settings: Enable/Disable, delivery fee, minimum order value, estimated delivery time.
   - Pickup settings: Enable/Disable, estimated ready time (e.g. "15–20 minutes").
8. **Test AI ordering & activate service**:
   - Use the built-in **Web Chat Simulator** (WhatsApp-style phone UI) inside the dashboard.
   - Test full journeys: browse menu → add to cart → checkout → see confirmation.
   - Once satisfied, toggle store status to **Live**.
9. **Manage incoming orders from dashboard**:
   - Real-time order feed with audio chime on new orders.
   - Kanban-style columns: **Pending → Preparing → Ready → Completed**.
   - One-click status update automatically sends WhatsApp message to customer.
   - Owner also receives a WhatsApp notification on their own registered phone when a new order arrives.

---

### Journey B: Customer (WhatsApp Interaction, 9 Steps)

1. **Customer sends a WhatsApp message** to the business number (e.g., *"Hi"*, *"Menu dikhao"*, *"I want to order"*, *"ما هو منيوكم؟"*).
2. **AI identifies language & intent**: Detects the language (English, Roman Urdu, Arabic) and classifies the intent:
   - `GREETING` → Welcome message + quick options (View Menu / Best Sellers / Place Order)
   - `SHOW_MENU` → Full formatted menu
   - `RECOMMEND` → Best sellers or items matching preference
   - `ADD_TO_CART` → Add items with quantity
   - `VIEW_CART` → Show current cart summary
   - `CHECKOUT` → Begin order placement
   - `CANCEL` → Cancel order or clear cart
3. **AI searches the business menu**: Pulls only active, available items for that specific tenant. Unavailable items are excluded automatically.
4. **Customer receives menu or recommendations**:
   - Menu is grouped by category with names, prices, and descriptions.
   - If customer asks *"What's your best thing?"*, AI replies with items flagged as `is_best_seller = true`.
5. **AI builds & updates cart**:
   - Customer: *"Give me 2 Mango Madness and 1 Avocado Shake"*
   - AI confirms each item, shows running subtotal, and asks: *"Anything else or shall I proceed to checkout?"*
   - Customer can add, remove, or change quantities at any point.
6. **Customer selects delivery or pickup**:
   - Interactive reply buttons: `📦 Delivery` / `🏪 Pickup`
   - If pickup is not enabled by the owner, only Delivery is offered (and vice versa).
7. **AI collects required details**:
   - For Delivery: customer name, full delivery address, any preparation notes.
   - For Pickup: customer name and preferred pickup time.
8. **Backend validates the final order**:
   - Checks all items are still available.
   - Checks the store is currently open (based on opening hours).
   - Calculates total: subtotal + delivery fee.
   - **If store is closed**: Responds with *"Sorry, Juice Island is currently closed. We open at 9:00 AM. Would you like to schedule an order?"*
   - **If item unavailable**: Responds with *"Sorry, Mango Madness is currently out of stock. Want a recommendation instead?"*
9. **Customer confirms & receives Order ID**:
   - AI shows full order summary and asks for confirmation.
   - Customer replies *"Confirm"* or taps the **✅ Confirm Order** button.
   - System assigns unique Order ID (e.g. `#OM-4821`), saves to database, pings the owner dashboard, and sends WhatsApp confirmation receipt to the customer.

---

## 4. Detailed Component Breakdown

### Phase 1: Database Models (`app/models/`)

| Model | Key Fields |
| :--- | :--- |
| `Tenant` | `id`, `slug`, `business_name`, `owner_email`, `hashed_password`, `is_verified`, `is_active`, `plan` |
| `WhatsAppConfig` | `tenant_id`, `phone_number_id`, `waba_id`, `access_token` (encrypted), `verify_token`, `webhook_url` |
| `StoreSettings` | `tenant_id`, `currency`, `delivery_enabled`, `pickup_enabled`, `delivery_fee`, `min_order_value`, `delivery_eta_mins`, `pickup_eta_mins` |
| `StoreHours` | `tenant_id`, `weekday` (0–6), `open_time`, `close_time`, `is_closed` |
| `Category` | `id`, `tenant_id`, `name`, `display_order`, `is_active` |
| `Product` | `id`, `tenant_id`, `category_id`, `name`, `description`, `price`, `is_available`, `is_best_seller`, `image_path` |
| `CartSession` | `tenant_id`, `customer_phone`, `state_step`, `cart_items` (JSON), `selected_type`, `customer_name`, `delivery_address`, `updated_at` |
| `Order` | `id`, `order_number`, `tenant_id`, `customer_phone`, `customer_name`, `order_type`, `delivery_address`, `status`, `subtotal`, `delivery_fee`, `total`, `notes`, `created_at` |
| `OrderItem` | `id`, `order_id`, `product_id`, `product_name`, `unit_price`, `quantity`, `subtotal` |

> **Cart Session Strategy**: DB-backed (`CartSession` table) for reliability. Sessions expire after 2 hours of inactivity. This ensures cart is not lost if the server restarts.

---

### Phase 2: Business Owner API & Portal (`app/api/routes/`)

| File | Endpoints |
| :--- | :--- |
| `auth.py` | `POST /auth/register`, `POST /auth/login`, `POST /auth/verify-email`, `GET /auth/me` |
| `tenants.py` | `GET/PUT /tenant/profile`, `POST /tenant/whatsapp-config`, `GET /tenant/webhook-info` |
| `menu.py` | `GET /menu`, `POST /menu/categories`, `POST/PUT/DELETE /menu/items/{id}`, `POST /menu/upload-csv`, `POST /menu/upload-item-image`, `POST /menu/ai-extract` |
| `orders.py` | `GET /orders`, `GET /orders/{id}`, `PATCH /orders/{id}/status` |
| `simulator.py` | `POST /simulator/chat` (stateless test endpoint, no DB writes) |

**UI Tech Stack**: Jinja2 templates + Tailwind CSS + Alpine.js (no separate frontend build needed; ships with FastAPI).

---

### Phase 3: File Storage (`/static/uploads/`)

```
/static/uploads/
  └── {tenant_id}/
        └── products/
              ├── product_42.jpg
              └── product_43.png
```

- **Dev**: Local disk storage at `/static/uploads/`.
- **Production**: Can be migrated to Cloudinary or AWS S3 by swapping the `FileStorageService`.
- Uploaded images are resized to max 800×800px using `Pillow` before saving (to keep WhatsApp-friendly file sizes).
- When a product image is sent via WhatsApp, the bot shares the image URL using Meta's media message API.

---

### Phase 4: Conversational AI & WhatsApp Engine (`app/services/`)

**`whatsapp_service.py`**:
- Verifies webhook token (`hub.challenge`).
- Parses incoming text messages, interactive button replies, and location messages.
- Sends: text messages, list menus, reply buttons, image messages, and order receipt templates.

**`ai_ordering_engine.py`**:
- Stateful conversation handler keyed by `(tenant_id, customer_phone)`.
- Intent detection using Google Gemini (with rule-based fallback for deterministic steps like checkout).
- Conversation state machine:
  ```
  IDLE → MENU_SHOWN → CART_BUILDING → CHECKOUT_TYPE → 
  COLLECTING_DETAILS → ORDER_CONFIRMATION → ORDER_PLACED
  ```
- Error handling:
  - Store closed → polite closed message with opening hours.
  - Item out of stock → suggestion of similar/available items.
  - Unrecognised message → friendly fallback with quick options.
  - Human handover → escalation message directing customer to call/WhatsApp owner directly.

---

### Phase 5: Owner Notifications

When a new order is placed:
1. **Dashboard**: Real-time update (SSE / polling) shows new order at the top of the queue with audio chime.
2. **WhatsApp Alert**: System sends a WhatsApp message to the owner's registered phone number:
   > *"🔔 New Order #OM-4821 from Ali!*
   > *2x Mango Madness, 1x Avocado Shake*
   > *Total: $14.98 — Delivery to: 4B Sunset Blvd*
   > *Reply CONFIRM or log in to dashboard."*

---

### Phase 6: Verification & Testing

**Automated Tests** (`python -m pytest tests/ -v`):

| Test File | What It Covers |
| :--- | :--- |
| `test_auth.py` | Register, login, JWT token, email verification |
| `test_menu.py` | Manual item creation, CSV upload parsing, image upload |
| `test_webhook.py` | Meta webhook token verification, message routing |
| `test_ai_engine.py` | Intent detection, cart add/remove/update, checkout flow |
| `test_orders.py` | Order creation, status transitions, multi-tenant isolation |
| `test_store_hours.py` | Closed-store rejection, opening-hours boundary conditions |

**Manual Verification Checklist**:
- [ ] Register as "Juice Island" owner → verify email link works.
- [ ] Add menu via CSV → check all rows imported correctly, bad rows reported.
- [ ] Upload a menu photo → verify AI extracts items and prices.
- [ ] Upload product image → check resized to ≤800px, stored under correct tenant folder.
- [ ] In Simulator: type "Hi" → get welcome message.
- [ ] In Simulator: type "Show menu" → see grouped categories.
- [ ] In Simulator: type "What's your best juice?" → see best-sellers.
- [ ] In Simulator: order 2x Mango Madness, choose Delivery, give address, Confirm → verify order appears in dashboard.
- [ ] Dashboard: change order to "Preparing" → verify owner gets notified (WhatsApp message to owner phone).
- [ ] Test closed-store scenario: set hours to "Closed today" → customer gets correct rejection message.
- [ ] Test out-of-stock: mark item unavailable → bot suggests alternative.
