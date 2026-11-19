from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["Web UI"])

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/dashboard", response_class=HTMLResponse)
def get_dashboard(request: Request):
    """
    Renders the OrderMate AI Business Owner Self-Service Dashboard & WhatsApp Simulator.
    """
    return templates.TemplateResponse(request=request, name="dashboard.html")
