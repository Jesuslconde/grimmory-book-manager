import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(override=False)
except ImportError:
    pass

GRIMMORY_URL = os.getenv("GRIMMORY_URL", "")
GRIMMORY_USERNAME = os.getenv("GRIMMORY_USERNAME", "")
GRIMMORY_PASSWORD = os.getenv("GRIMMORY_PASSWORD", "")

QBIT_URL = os.getenv("QBIT_URL", "")
QBIT_USERNAME = os.getenv("QBIT_USERNAME", "")
QBIT_PASSWORD = os.getenv("QBIT_PASSWORD", "")

JACKETT_URL = os.getenv("JACKETT_URL", "")
JACKETT_API_KEY = os.getenv("JACKETT_API_KEY", "")

BOOKDROP_FOLDER = os.getenv("BOOKDROP_FOLDER", "")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "300"))

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8099"))

DB_PATH = os.getenv("DB_PATH", "data/bookmanager.db")

def _read_version() -> str:
    try:
        return Path(__file__).parent.joinpath("VERSION").read_text().strip()
    except FileNotFoundError:
        return "dev"

VERSION = os.getenv("VERSION", _read_version())
