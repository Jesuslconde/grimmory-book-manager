import html
import json
import logging

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from database import get_db
from settings_service import get_all_settings
from clients.jackett_client import JackettClient
from clients.grimmory_client import GrimmoryClient
from services.search_service import SearchService

logger = logging.getLogger(__name__)

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


@router.get("/api/search")
async def search(
    request: Request,
    q: str = Query(""),
    indexer: str = Query("epublibre"),
):
    if not q.strip():
        return HTMLResponse("")

    db = next(get_db())
    settings = get_all_settings(db)

    jackett_url = settings.get("jackett_url", "")
    jackett_key = settings.get("jackett_api_key", "")

    if not jackett_url or not jackett_key:
        logger.warning("Jackett not configured: url=%s key=%s", jackett_url, bool(jackett_key))
        return HTMLResponse('<div class="empty-state">Configura Jackett en la pantalla de configuracion</div>')

    jackett = JackettClient(base_url=jackett_url, api_key=jackett_key)
    grimmory = GrimmoryClient(
        base_url=settings.get("grimmory_url", ""),
        username=settings.get("grimmory_username", ""),
        password=settings.get("grimmory_password", ""),
    )

    logger.info("Searching Jackett: query='%s' indexer='%s'", q, indexer)
    svc = SearchService(jackett, grimmory)
    results = svc.search(q, indexer=indexer, db=db)
    logger.info("Search returned %d results", len(results))

    html_parts = []
    for r in results:
        size = _fmt_size(r.jackett.size_bytes)
        badge = ""
        if r.in_library:
            badge = '<span class="badge badge-green">En biblioteca</span>'
        elif r.already_downloaded:
            badge = '<span class="badge badge-yellow">Ya descargado</span>'

        seeders_class = "text-green" if r.jackett.seeders > 10 else "text-yellow" if r.jackett.seeders > 0 else "text-red"

        hx_vals = html.escape(json.dumps({"download_url": r.jackett.download_url, "title": r.jackett.title}))
        logger.info("Search result: title=%r download_url=%r hx_vals=%r", r.jackett.title, r.jackett.download_url, hx_vals)
        html_parts.append(f"""
        <div class="result-card">
            <div class="result-header">
                <strong>{r.jackett.title}</strong>
                {badge}
            </div>
            <div class="result-meta">
                <span>{size}</span>
                <span class="{seeders_class}">Seeders: {r.jackett.seeders}</span>
                <span>Leechers: {r.jackett.leechers}</span>
                <span class="badge badge-blue">{r.jackett.indexer}</span>
            </div>
            <div class="result-actions">
                <button class="btn btn-primary"
                        hx-post="/api/downloads"
                        hx-vals='{hx_vals}'
                        hx-target="#download-feedback"
                        hx-swap="innerHTML">
                    Descargar
                </button>
            </div>
        </div>
        """)

    if not html_parts:
        return HTMLResponse('<div class="empty-state">No se encontraron resultados</div>')

    return HTMLResponse("\n".join(html_parts))
