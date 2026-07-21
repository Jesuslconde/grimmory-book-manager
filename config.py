import os
from dotenv import load_dotenv

load_dotenv()

GRIMMORY_URL = os.getenv("GRIMMORY_URL", "http://localhost:61987")
GRIMMORY_USERNAME = os.getenv("GRIMMORY_USERNAME", "admin")
GRIMMORY_PASSWORD = os.getenv("GRIMMORY_PASSWORD", "")

QBIT_URL = os.getenv("QBIT_URL", "http://localhost:8080")
QBIT_USERNAME = os.getenv("QBIT_USERNAME", "admin")
QBIT_PASSWORD = os.getenv("QBIT_PASSWORD", "")

JACKETT_URL = os.getenv("JACKETT_URL", "http://localhost:9117")
JACKETT_API_KEY = os.getenv("JACKETT_API_KEY", "")

BOOKDROP_FOLDER = os.getenv("BOOKDROP_FOLDER", "/bookdrop")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "300"))

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

DB_PATH = os.getenv("DB_PATH", "data/bookmanager.db")
