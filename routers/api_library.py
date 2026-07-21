from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from database import get_db
from settings_service import get_all_settings
from clients.grimmory_client import GrimmoryClient

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def _fmt_size(kb: float) -> str:
    if kb <= 0:
        return "?"
    val = float(kb)
    units = ["KB", "MB", "GB"]
    for unit in units:
        if val < 1024:
            return f"{val:.1f} {unit}"
        val /= 1024
    return f"{val:.1f} TB"


def _status_badge(status: str) -> str:
    colors = {
        "READ": "badge-green",
        "READING": "badge-blue",
        "RE_READING": "badge-blue",
        "UNREAD": "badge-gray",
        "UNSET": "badge-gray",
        "PARTIALLY_READ": "badge-yellow",
        "PAUSED": "badge-yellow",
    }
    cls = colors.get(status, "badge-gray")
    return f'<span class="badge {cls}">{status}</span>'


@router.get("/api/library")
async def list_library(
    request: Request,
    q: str = Query(""),
    file_type: str = Query(""),
):
    db = next(get_db())
    settings = get_all_settings(db)

    grimmory = GrimmoryClient(
        base_url=settings.get("grimmory_url", ""),
        username=settings.get("grimmory_username", ""),
        password=settings.get("grimmory_password", ""),
    )

    try:
        if q.strip():
            books = grimmory.search_books(q)
        else:
            books = grimmory.get_books()
    except Exception as e:
        return HTMLResponse(f'<div class="empty-state">Error conectando con Grimmory: {e}</div>')

    if file_type:
        books = [b for b in books if b.file_type.upper() == file_type.upper()]

    if not books:
        return HTMLResponse('<div class="empty-state">No se encontraron libros</div>')

    html_parts = []
    for b in books:
        authors = ", ".join(b.authors[:3]) if b.authors else "Desconocido"
        series = ""
        if b.series_name:
            series = f'<span class="badge badge-blue">{b.series_name} #{b.series_number or "?"}</span>'

        html_parts.append(f"""
        <div class="book-card">
            <div class="book-header">
                <strong>{b.title}</strong>
                {_status_badge(b.read_status)}
            </div>
            <div class="book-meta">
                <span>{authors}</span>
                {series}
                <span class="badge badge-gray">{b.file_type}</span>
            </div>
            <div class="book-footer">
                <span class="text-muted">{b.file_name}</span>
            </div>
        </div>
        """)

    return HTMLResponse("\n".join(html_parts))
