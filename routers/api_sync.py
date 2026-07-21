from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from database import get_db
from settings_service import get_all_settings
from clients.qbit_client import QBitClient
from clients.grimmory_client import GrimmoryClient
from services.sync_service import SyncService

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/api/sync/status")
async def sync_status():
    return HTMLResponse("OK")


@router.post("/api/sync/force")
async def force_sync():
    db = next(get_db())
    settings = get_all_settings(db)

    qbit = QBitClient(
        base_url=settings.get("qbit_url", ""),
        username=settings.get("qbit_username", ""),
        password=settings.get("qbit_password", ""),
    )
    grimmory = GrimmoryClient(
        base_url=settings.get("grimmory_url", ""),
        username=settings.get("grimmory_username", ""),
        password=settings.get("grimmory_password", ""),
    )

    svc = SyncService(qbit, grimmory)
    bookdrop = settings.get("bookdrop_folder", "/bookdrop")
    auto_update = settings.get("auto_update_path", "true") == "true"

    events = svc.run_sync_cycle(bookdrop_folder=bookdrop, auto_update=auto_update, db=db)

    if not events:
        return HTMLResponse('<div class="empty-state">Sin cambios</div>')

    html_parts = []
    for e in events:
        html_parts.append(f"""
        <div class="event-card">
            <span class="badge badge-green">{e['event_type']}</span>
            <strong>{e.get('book_title', '?')}</strong>
            <span class="text-muted">{e['old_path']} &rarr; {e['new_path']}</span>
        </div>
        """)

    return HTMLResponse("\n".join(html_parts))


@router.get("/api/activity")
async def list_activity(request: Request):
    db = next(get_db())
    settings = get_all_settings(db)

    qbit = QBitClient(
        base_url=settings.get("qbit_url", ""),
        username=settings.get("qbit_username", ""),
        password=settings.get("qbit_password", ""),
    )
    grimmory = GrimmoryClient(
        base_url=settings.get("grimmory_url", ""),
        username=settings.get("grimmory_username", ""),
        password=settings.get("grimmory_password", ""),
    )

    svc = SyncService(qbit, grimmory)
    events = svc.get_sync_events(limit=100, db=db)

    if not events:
        return HTMLResponse('<div class="empty-state">No hay eventos de sincronizacion</div>')

    html_parts = []
    for e in events:
        ts = e["created_at"][:19].replace("T", " ") if e["created_at"] else "?"
        html_parts.append(f"""
        <div class="event-card">
            <span class="badge badge-blue">{e['event_type']}</span>
            <span>Book #{e.get('book_id', '?')}</span>
            <span class="text-muted">{e.get('old_value', '')} &rarr; {e.get('new_value', '')}</span>
            <span class="text-muted">{ts}</span>
        </div>
        """)

    return HTMLResponse("\n".join(html_parts))
