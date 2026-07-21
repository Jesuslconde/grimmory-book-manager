from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from database import get_db
from settings_service import get_all_settings, save_settings
from clients.jackett_client import JackettClient
from clients.qbit_client import QBitClient
from clients.grimmory_client import GrimmoryClient

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.post("/api/settings")
async def post_settings(
    grimmory_url: str = Form(""),
    grimmory_username: str = Form(""),
    grimmory_password: str = Form(""),
    qbit_url: str = Form(""),
    qbit_username: str = Form(""),
    qbit_password: str = Form(""),
    jackett_url: str = Form(""),
    jackett_api_key: str = Form(""),
    bookdrop_folder: str = Form(""),
    poll_interval: str = Form("300"),
    auto_update_path: str = Form("false"),
    notify_on_sync: str = Form("false"),
):
    db = next(get_db())
    data = {
        "grimmory_url": grimmory_url,
        "grimmory_username": grimmory_username,
        "grimmory_password": grimmory_password,
        "qbit_url": qbit_url,
        "qbit_username": qbit_username,
        "qbit_password": qbit_password,
        "jackett_url": jackett_url,
        "jackett_api_key": jackett_api_key,
        "bookdrop_folder": bookdrop_folder,
        "poll_interval": poll_interval,
        "auto_update_path": "true" if auto_update_path == "on" else "false",
        "notify_on_sync": "true" if notify_on_sync == "on" else "false",
    }
    save_settings(db, data)
    return HTMLResponse('<span style="color:green">Configuracion guardada</span>')


@router.post("/api/settings/test/{service}")
async def test_connection(service: str):
    db = next(get_db())
    settings = get_all_settings(db)

    if service == "grimmory":
        client = GrimmoryClient(
            base_url=settings.get("grimmory_url", ""),
            username=settings.get("grimmory_username", ""),
            password=settings.get("grimmory_password", ""),
        )
        ok, msg = client.test_connection()
    elif service == "qbit":
        client = QBitClient(
            base_url=settings.get("qbit_url", ""),
            username=settings.get("qbit_username", ""),
            password=settings.get("qbit_password", ""),
        )
        ok, msg = client.test_connection()
    elif service == "jackett":
        client = JackettClient(
            base_url=settings.get("jackett_url", ""),
            api_key=settings.get("jackett_api_key", ""),
        )
        ok, msg = client.test_connection()
    else:
        return HTMLResponse('<span style="color:red">Servicio desconocido</span>')

    color = "green" if ok else "red"
    prefix = "\u2713" if ok else "\u2717"
    return HTMLResponse(f'<span style="color:{color}">{prefix} {msg}</span>')
