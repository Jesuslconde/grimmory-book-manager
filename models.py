from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func

from database import Base


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String, primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Download(Base):
    __tablename__ = "downloads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    torrent_hash = Column(String, unique=True)
    title = Column(Text, nullable=False)
    download_url = Column(Text, nullable=False)
    save_path = Column(Text)
    status = Column(String, default="pending")
    grimmory_book_id = Column(Integer)
    added_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime)


class SyncEvent(Base):
    __tablename__ = "sync_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    torrent_hash = Column(String)
    book_id = Column(Integer)
    event_type = Column(Text, nullable=False)
    old_value = Column(Text)
    new_value = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
