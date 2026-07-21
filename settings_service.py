from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from models import Setting


class SettingsService:
    def __init__(self, engine: Engine):
        self.engine = engine
        self._session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def get(self, key: str, default: str = "") -> str:
        with self._session_factory() as db:
            row = db.query(Setting).filter(Setting.key == key).first()
            return row.value if row else default

    def get_all(self) -> dict[str, str]:
        with self._session_factory() as db:
            rows = db.query(Setting).all()
            return {row.key: row.value for row in rows}

    def save(self, data: dict[str, str]) -> None:
        with self._session_factory() as db:
            for key, value in data.items():
                existing = db.query(Setting).filter(Setting.key == key).first()
                if existing:
                    existing.value = str(value)
                else:
                    db.add(Setting(key=key, value=str(value)))
            db.commit()

    def _get_all_dict(self) -> dict[str, str]:
        return self.get_all()


def get_all_settings(db: Session) -> dict[str, str]:
    rows = db.query(Setting).all()
    return {row.key: row.value for row in rows}


def get_setting(db: Session, key: str, default: str = "") -> str:
    row = db.query(Setting).filter(Setting.key == key).first()
    return row.value if row else default


def save_settings(db: Session, data: dict[str, str]) -> None:
    for key, value in data.items():
        existing = db.query(Setting).filter(Setting.key == key).first()
        if existing:
            existing.value = str(value)
        else:
            db.add(Setting(key=key, value=str(value)))
    db.commit()
