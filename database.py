from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

from config import DB_PATH

Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS downloads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    torrent_hash TEXT UNIQUE,
    title TEXT NOT NULL,
    download_url TEXT NOT NULL,
    save_path TEXT,
    status TEXT DEFAULT 'pending',
    grimmory_book_id INTEGER,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sync_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    torrent_hash TEXT,
    book_id INTEGER,
    event_type TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

DEFAULT_SETTINGS = {
    "grimmory_url": "",
    "grimmory_username": "",
    "grimmory_password": "",
    "qbit_url": "",
    "qbit_username": "",
    "qbit_password": "",
    "jackett_url": "",
    "jackett_api_key": "",
    "bookdrop_folder": "",
    "poll_interval": "300",
    "auto_update_path": "true",
    "notify_on_sync": "true",
}


def init_db():
    with engine.connect() as conn:
        for statement in SCHEMA.split(";"):
            stmt = statement.strip()
            if stmt:
                conn.execute(text(stmt))
        for key, value in DEFAULT_SETTINGS.items():
            conn.execute(
                text("INSERT OR IGNORE INTO settings (key, value) VALUES (:key, :value)"),
                {"key": key, "value": value},
            )
        conn.commit()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
