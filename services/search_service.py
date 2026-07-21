from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from clients.jackett_client import JackettClient, SearchResult
from clients.grimmory_client import GrimmoryClient, BookSummary
from models import Download

logger = logging.getLogger(__name__)


@dataclass
class EnrichedResult:
    jackett: SearchResult
    already_downloaded: bool
    in_library: bool
    library_book: BookSummary | None


class SearchService:
    def __init__(self, jackett: JackettClient, grimmory: GrimmoryClient):
        self.jackett = jackett
        self.grimmory = grimmory

    def search(
        self,
        query: str,
        indexer: str = "epublibre",
        db: Session | None = None,
    ) -> list[EnrichedResult]:
        results = self.jackett.search(query, indexer=indexer)

        library_books: list[BookSummary] = []
        try:
            library_books = self.grimmory.get_books()
        except Exception:
            logger.warning("Could not fetch Grimmory library for dedup check")

        library_by_filename = {b.file_name.lower(): b for b in library_books}

        downloaded_hashes: set[str] = set()
        if db:
            downloads = db.query(Download).all()
            downloaded_hashes = {d.torrent_hash for d in downloads if d.torrent_hash}

        enriched = []
        for result in results:
            filename = result.title.lower()
            in_library = filename in library_by_filename

            library_book = library_by_filename.get(filename)
            already_downloaded = any(
                result.title.lower() in (d.title or "").lower()
                for d in (db.query(Download).all() if db else [])
            )

            enriched.append(EnrichedResult(
                jackett=result,
                already_downloaded=already_downloaded,
                in_library=in_library,
                library_book=library_book,
            ))

        return enriched

    def get_indexers(self) -> list[dict[str, str]]:
        return self.jackett.get_indexers()
