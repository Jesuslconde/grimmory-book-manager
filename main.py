import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from database import init_db, engine
from settings_service import SettingsService
from routers import pages, api_settings, api_search, api_downloads, api_library, api_sync

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

sync_task: asyncio.Task | None = None


def _is_configured(settings: SettingsService) -> bool:
    s = settings.get_all()
    return bool(s.get("qbit_url")) and bool(s.get("grimmory_url"))


async def run_sync_loop(settings: SettingsService):
    while True:
        try:
            if not _is_configured(settings):
                await asyncio.sleep(30)
                continue

            from clients.qbit_client import QBitClient
            from clients.grimmory_client import GrimmoryClient
            from services.sync_service import SyncService

            s = settings.get_all()
            qbit = QBitClient(
                base_url=s.get("qbit_url", ""),
                username=s.get("qbit_username", ""),
                password=s.get("qbit_password", ""),
            )
            grimmory = GrimmoryClient(
                base_url=s.get("grimmory_url", ""),
                username=s.get("grimmory_username", ""),
                password=s.get("grimmory_password", ""),
            )

            svc = SyncService(qbit, grimmory)
            bookdrop = s.get("bookdrop_folder", "/bookdrop")
            auto_update = s.get("auto_update_path", "true").lower() == "true"

            await asyncio.to_thread(svc.run_sync_cycle, bookdrop, auto_update)
        except Exception as e:
            logger.error("sync error: %s", e)

        try:
            interval = int(settings.get("poll_interval", "300"))
        except (ValueError, TypeError):
            interval = 300
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    settings = SettingsService(engine)
    app.state.settings_svc = settings

    global sync_task
    sync_task = asyncio.create_task(run_sync_loop(settings))
    logger.info("Sync loop started (will skip until services are configured)")

    yield

    if sync_task:
        sync_task.cancel()
        try:
            await sync_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Grimmory Book Manager", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

app.include_router(pages.router)
app.include_router(api_settings.router)
app.include_router(api_search.router)
app.include_router(api_downloads.router)
app.include_router(api_library.router)
app.include_router(api_sync.router)


@app.get("/health")
def health():
    return {"status": "ok"}
