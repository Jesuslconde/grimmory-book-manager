from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from database import get_db
from settings_service import get_all_settings
from clients.qbit_client import QBitClient
from services.download_service import DownloadService

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def _fmt_size(size_bytes: int) -> str:
    if size_bytes <= 0:
        return "?"
    units = ["B", "KB", "MB", "GB", "TB"]
    val = float(size_bytes)
    for unit in units:
        if val < 1024:
            return f"{val:.1f} {unit}"
        val /= 1024
    return f"{val:.1f} PB"


def _fmt_speed(speed_bps: int) -> str:
    if speed_bps <= 0:
        return "0 B/s"
    return _fmt_size(speed_bps) + "/s"


def _state_label(state: str) -> str:
    labels = {
        "downloading": "Descargando",
        "stalledDL": "Stalled",
        "queuedDL": "En cola",
        "uploading": "Seedando",
        "stalledUP": "Seedando (idle)",
        "queuedUP": "Seedando (cola)",
        "pausedDL": "Pausado",
        "pausedUP": "Pausado",
        "checking": "Verificando",
        "missingfiles": "Archivos perdidos",
        "error": "Error",
    }
    return labels.get(state, state)


def _state_class(state: str) -> str:
    if state in ("downloading", "stalledDL", "queuedDL"):
        return "text-blue"
    if state in ("uploading", "stalledUP", "queuedUP"):
        return "text-green"
    if "paused" in state:
        return "text-yellow"
    if state in ("missingfiles", "error"):
        return "text-red"
    return ""


class DownloadRequest(BaseModel):
    download_url: str
    title: str


@router.post("/api/downloads")
async def add_download(request: Request, download_url: str = "", title: str = ""):
    db = next(get_db())
    settings = get_all_settings(db)

    qbit = QBitClient(
        base_url=settings.get("qbit_url", ""),
        username=settings.get("qbit_username", ""),
        password=settings.get("qbit_password", ""),
    )
    svc = DownloadService(qbit)
    bookdrop = settings.get("bookdrop_folder", "/bookdrop")

    download = svc.add_download(download_url=download_url, title=title, save_path=bookdrop, db=db)

    if download:
        return HTMLResponse(f"""
        <div class="toast toast-success">
            Añadido: {title}
        </div>
        """)
    return HTMLResponse(f"""
    <div class="toast toast-error">
        Error al añadir: {title}
    </div>
    """)


@router.delete("/api/downloads/{torrent_hash}")
async def remove_download(torrent_hash: str, delete_files: bool = False):
    db = next(get_db())
    settings = get_all_settings(db)

    qbit = QBitClient(
        base_url=settings.get("qbit_url", ""),
        username=settings.get("qbit_username", ""),
        password=settings.get("qbit_password", ""),
    )
    svc = DownloadService(qbit)
    success = svc.remove_download(torrent_hash, delete_files=delete_files, db=db)

    if success:
        return HTMLResponse("")
    return HTMLResponse('<span class="text-red">Error al eliminar</span>', status_code=500)


@router.post("/api/downloads/{torrent_hash}/pause")
async def pause_download(torrent_hash: str):
    db = next(get_db())
    settings = get_all_settings(db)
    qbit = QBitClient(
        base_url=settings.get("qbit_url", ""),
        username=settings.get("qbit_username", ""),
        password=settings.get("qbit_password", ""),
    )
    DownloadService(qbit).pause_download(torrent_hash)
    return HTMLResponse("")


@router.post("/api/downloads/{torrent_hash}/resume")
async def resume_download(torrent_hash: str):
    db = next(get_db())
    settings = get_all_settings(db)
    qbit = QBitClient(
        base_url=settings.get("qbit_url", ""),
        username=settings.get("qbit_username", ""),
        password=settings.get("qbit_password", ""),
    )
    DownloadService(qbit).resume_download(torrent_hash)
    return HTMLResponse("")


@router.get("/api/downloads")
async def list_downloads(request: Request):
    db = next(get_db())
    settings = get_all_settings(db)

    qbit = QBitClient(
        base_url=settings.get("qbit_url", ""),
        username=settings.get("qbit_username", ""),
        password=settings.get("qbit_password", ""),
    )
    svc = DownloadService(qbit)
    downloads = svc.get_active_downloads(db)

    if not downloads:
        return HTMLResponse('<div class="empty-state">No hay descargas activas</div>')

    html_parts = []
    for d in downloads:
        progress_pct = int(d["progress"] * 100)
        speed = _fmt_speed(d["dlspeed"]) if d["state"] not in ("uploading", "stalledUP", "queuedUP") else _fmt_speed(d["upspeed"])
        state_label = _state_label(d["state"])
        state_cls = _state_class(d["state"])
        size = _fmt_size(d["size"])

        html_parts.append(f"""
        <div class="download-card">
            <div class="download-header">
                <strong>{d['name']}</strong>
                <span class="{state_cls}">{state_label}</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" style="width: {progress_pct}%"></div>
            </div>
            <div class="download-meta">
                <span>{progress_pct}%</span>
                <span>{size}</span>
                <span>{speed}</span>
                <span>Ratio: {d['ratio']:.2f}</span>
                <span>Seeds: {d['num_seeds']}</span>
            </div>
            <div class="download-actions">
                <button class="btn btn-sm"
                        hx-post="/api/downloads/{d['hash']}/resume"
                        hx-target="closest .download-card">Reanudar</button>
                <button class="btn btn-sm"
                        hx-post="/api/downloads/{d['hash']}/pause"
                        hx-target="closest .download-card">Pausar</button>
                <button class="btn btn-sm btn-danger"
                        hx-delete="/api/downloads/{d['hash']}"
                        hx-confirm="Eliminar este torrent?"
                        hx-target="closest .download-card"
                        hx-swap="outerHTML">Eliminar</button>
            </div>
        </div>
        """)

    return HTMLResponse("\n".join(html_parts))
