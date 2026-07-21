from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from database import get_db, engine
from settings_service import get_all_settings, SettingsService
from services.download_service import DownloadService
from services.sync_service import SyncService
from clients.qbit_client import QBitClient
from clients.grimmory_client import GrimmoryClient

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def _is_configured(settings: dict) -> bool:
    return bool(settings.get("qbit_url")) and bool(settings.get("grimmory_url"))


@router.get("/")
async def dashboard(request: Request):
    db = next(get_db())
    settings = get_all_settings(db)
    configured = _is_configured(settings)

    download_status = {"total": 0, "downloading": 0, "seeding": 0, "paused": 0, "completed": 0}
    recent_events = []

    if configured:
        grimmory = GrimmoryClient(
            base_url=settings.get("grimmory_url", ""),
            username=settings.get("grimmory_username", ""),
            password=settings.get("grimmory_password", ""),
        )
        qbit = QBitClient(
            base_url=settings.get("qbit_url", ""),
            username=settings.get("qbit_username", ""),
            password=settings.get("qbit_password", ""),
        )

        download_svc = DownloadService(qbit)
        sync_svc = SyncService(qbit, grimmory)

        try:
            download_status = download_svc.sync_status(db)
        except Exception:
            pass

        try:
            recent_events = sync_svc.get_sync_events(limit=5, db=db)
        except Exception:
            pass

    return templates.TemplateResponse(request, "dashboard.html", {
        "configured": configured,
        "download_status": download_status,
        "recent_events": recent_events,
    })


@router.get("/search")
async def search_page(request: Request):
    return templates.TemplateResponse(request, "search.html", {})


@router.get("/downloads")
async def downloads_page(request: Request):
    return templates.TemplateResponse(request, "downloads.html", {})


@router.get("/library")
async def library_page(request: Request):
    return templates.TemplateResponse(request, "library.html", {})


@router.get("/activity")
async def activity_page(request: Request):
    return templates.TemplateResponse(request, "activity.html", {})


@router.get("/settings")
async def settings_page(request: Request):
    db = next(get_db())
    settings = get_all_settings(db)
    return templates.TemplateResponse(request, "settings.html", {"settings": settings})
