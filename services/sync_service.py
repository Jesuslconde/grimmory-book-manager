from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from clients.grimmory_client import GrimmoryClient
from clients.qbit_client import QBitClient
from models import Download, SyncEvent

logger = logging.getLogger(__name__)


class SyncService:
    def __init__(self, qbit: QBitClient, grimmory: GrimmoryClient):
        self.qbit = qbit
        self.grimmory = grimmory

    def run_sync_cycle(self, bookdrop_folder: str, auto_update: bool, db: Session | None = None) -> list[dict]:
        events = []

        try:
            self.qbit._get_session()
            self.grimmory.login()
        except Exception as e:
            logger.error("Sync cycle skipped, service login failed: %s", e)
            return events

        try:
            torrents = self.qbit.get_torrents()
        except Exception as e:
            logger.error("Failed to fetch torrents: %s", e)
            return events

        try:
            books = self.grimmory.get_books()
        except Exception as e:
            logger.error("Failed to fetch Grimmory books: %s", e)
            return events

        books_by_filename = {}
        for book in books:
            if book.file_name:
                books_by_filename[book.file_name.lower()] = book

        for torrent in torrents:
            save_path = torrent.save_path
            if not save_path or not save_path.startswith(bookdrop_folder):
                continue

            files = []
            try:
                files = self.qbit.get_torrent_files(torrent.hash)
            except Exception:
                continue

            for tf in files:
                file_name = tf.get("name", "")
                full_path = os.path.join(save_path, file_name)

                if os.path.exists(full_path):
                    continue

                book = books_by_filename.get(file_name.lower())
                if not book:
                    logger.info("No matching Grimmory book for moved file: %s", file_name)
                    continue

                new_dir = os.path.dirname(book.file_path)
                if not new_dir:
                    continue

                if auto_update:
                    success = self.qbit.set_location(torrent.hash, new_dir)
                    if success:
                        self.qbit.recheck(torrent.hash)

                        if db:
                            download = db.query(Download).filter(Download.torrent_hash == torrent.hash).first()
                            if download:
                                download.status = "completed"
                                download.grimmory_book_id = book.id
                                download.completed_at = datetime.now(timezone.utc)

                            event = SyncEvent(
                                torrent_hash=torrent.hash,
                                book_id=book.id,
                                event_type="path_updated",
                                old_value=save_path,
                                new_value=new_dir,
                            )
                            db.add(event)
                            db.commit()

                        events.append({
                            "torrent_hash": torrent.hash,
                            "torrent_name": torrent.name,
                            "book_id": book.id,
                            "book_title": book.title,
                            "old_path": save_path,
                            "new_path": new_dir,
                            "event_type": "path_updated",
                        })

                        logger.info("Updated torrent %s path: %s -> %s", torrent.name, save_path, new_dir)

        return events

    def get_sync_events(self, limit: int = 100, db: Session | None = None) -> list[dict]:
        if not db:
            return []

        events = (
            db.query(SyncEvent)
            .order_by(SyncEvent.created_at.desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "id": e.id,
                "torrent_hash": e.torrent_hash,
                "book_id": e.book_id,
                "event_type": e.event_type,
                "old_value": e.old_value,
                "new_value": e.new_value,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ]
