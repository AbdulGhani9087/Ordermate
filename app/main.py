from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.db.database import create_db_and_tables
from app.api.routes.auth import router as auth_router
from app.api.routes.tenants import router as tenants_router
from app.api.routes.menu import router as menu_router
from app.api.routes.orders import router as orders_router
from app.api.routes.webhook import router as webhook_router
from app.api.routes.simulator import router as simulator_router

# ── Lifespan event handler ────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create all DB tables
    create_db_and_tables()
    yield
    # Shutdown logic (if any)

# ── App instance ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="OrderMate AI",
    description="Multi-tenant Self-Service WhatsApp Ordering SaaS",
    version="0.1.0",
    lifespan=lifespan,
)

# ── Static files (uploaded images, CSS, JS) ───────────────────────────────────
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)
UPLOADS_DIR = STATIC_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ── Include API Routers ───────────────────────────────────────────────────────
API_V1_PREFIX = "/api/v1"
app.include_router(auth_router, prefix=API_V1_PREFIX)
app.include_router(tenants_router, prefix=API_V1_PREFIX)
app.include_router(menu_router, prefix=API_V1_PREFIX)
app.include_router(orders_router, prefix=API_V1_PREFIX)
app.include_router(webhook_router, prefix=API_V1_PREFIX)
app.include_router(simulator_router, prefix=API_V1_PREFIX)

# ── Health & root ──────────────────────────────────────────────────────────────
@app.get("/")
def home():
    return {
        "message": "Welcome to OrderMate AI",
        "status": "running",
        "version": "0.1.0",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}
