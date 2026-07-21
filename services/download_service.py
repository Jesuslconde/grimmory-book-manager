from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from clients.qbit_client import QBitClient
from models import Download, SyncEvent

logger = logging.getLogger(__name__)


class DownloadService:
    def __init__(self, qbit: QBitClient):
        self.qbit = qbit

    def add_download(
        self,
        download_url: str,
        title: str,
        save_path: str = "/bookdrop",
        db: Session | None = None,
    ) -> Download | None:
        success = self.qbit.add_torrent(urls=download_url, save_path=save_path, tags="grimmory")
        if not success:
            return None

        if db:
            existing = db.query(Download).filter(Download.title == title).first()
            if existing:
                existing.download_url = download_url
                existing.status = "downloading"
                existing.save_path = save_path
                db.commit()
                db.refresh(existing)
                return existing

            download = Download(
                title=title,
                download_url=download_url,
                save_path=save_path,
                status="downloading",
            )
            db.add(download)
            db.commit()
            db.refresh(download)
            return download

        return Download(title=title, download_url=download_url, save_path=save_path, status="downloading")

    def remove_download(self, torrent_hash: str, delete_files: bool = False, db: Session | None = None) -> bool:
        success = self.qbit.delete_torrent(torrent_hash, delete_files=delete_files)
        if success and db:
            download = db.query(Download).filter(Download.torrent_hash == torrent_hash).first()
            if download:
                db.delete(download)
                db.commit()
        return success

    def pause_download(self, torrent_hash: str) -> bool:
        return self.qbit.pause_torrent(torrent_hash)

    def resume_download(self, torrent_hash: str) -> bool:
        return self.qbit.resume_torrent(torrent_hash)

    def get_active_downloads(self, db: Session | None = None) -> list[dict]:
        try:
            torrents = self.qbit.get_torrents(category=None)
        except Exception:
            logger.warning("Could not fetch torrents from qBittorrent")
            return []

        grimmory_torrents = [t for t in torrents if t.state not in ("missingfiles",)]

        result = []
        for t in grimmory_torrents:
            db_download = None
            if db:
                db_download = db.query(Download).filter(Download.torrent_hash == t.hash).first()

            result.append({
                "hash": t.hash,
                "name": t.name,
                "save_path": t.save_path,
                "state": t.state,
                "progress": t.progress,
                "dlspeed": t.dlspeed,
                "upspeed": t.upspeed,
                "ratio": t.ratio,
                "num_seeds": t.num_seeds,
                "size": t.size,
                "grimmory_book_id": db_download.grimmory_book_id if db_download else None,
                "db_status": db_download.status if db_download else "untracked",
            })

        return result

    def sync_status(self, db: Session | None = None) -> dict:
        downloads = self.get_active_downloads(db)
        return {
            "total": len(downloads),
            "downloading": sum(1 for d in downloads if d["state"] in ("downloading", "stalledDL", "queuedDL")),
            "seeding": sum(1 for d in downloads if d["state"] in ("uploading", "stalledUP", "queuedUP")),
            "paused": sum(1 for d in downloads if "paused" in d["state"]),
            "completed": sum(1 for d in downloads if d["progress"] >= 1.0),
        }
