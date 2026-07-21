from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass
class BookSummary:
    id: int
    title: str
    authors: list[str]
    file_name: str
    file_path: str
    file_type: str
    library_id: int
    library_name: str
    read_status: str
    series_name: str | None
    series_number: float | None
    added_on: str


class GrimmoryClient:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self._access_token: str | None = None
        self._refresh_token: str | None = None

    def login(self) -> None:
        url = f"{self.base_url}/api/v1/auth/login"
        data = {"username": self.username, "password": self.password}

        try:
            response = httpx.post(url, json=data, timeout=10)
            response.raise_for_status()
            body = response.json()
            self._access_token = body["accessToken"]
            self._refresh_token = body["refreshToken"]
        except Exception as e:
            logger.error("Grimmory login failed: %s", e)
            self._access_token = None
            raise

    def _refresh(self) -> None:
        if not self._refresh_token:
            self.login()
            return

        url = f"{self.base_url}/api/v1/auth/refresh"
        data = {"refreshToken": self._refresh_token}

        try:
            response = httpx.post(url, json=data, timeout=10)
            response.raise_for_status()
            body = response.json()
            self._access_token = body["accessToken"]
            self._refresh_token = body["refreshToken"]
        except Exception:
            self.login()

    def _headers(self) -> dict[str, str]:
        if not self._access_token:
            self.login()
        return {"Authorization": f"Bearer {self._access_token}"}

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        url = f"{self.base_url}{path}"

        try:
            response = httpx.request(method, url, headers=self._headers(), timeout=15, **kwargs)
            if response.status_code == 401:
                self._refresh()
                response = httpx.request(method, url, headers=self._headers(), timeout=15, **kwargs)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                self.login()
                response = httpx.request(method, url, headers=self._headers(), timeout=15, **kwargs)
                response.raise_for_status()
                return response
            raise

    def test_connection(self) -> tuple[bool, str]:
        try:
            self.login()
            resp = self._request("GET", "/api/v1/healthcheck")
            data = resp.json()
            return True, f"Conectado (v{data.get('version', '?')})"
        except Exception as e:
            return False, str(e)

    def get_books(self) -> list[BookSummary]:
        response = self._request("GET", "/api/v1/books", params={"stripForListView": "false"})
        data = response.json()

        books = []
        for b in data:
            primary = b.get("primaryFile")
            if not primary:
                continue

            metadata = b.get("metadata", {})
            authors = []
            if metadata and metadata.get("authors"):
                authors = [a.get("name", "") for a in metadata["authors"]]

            series_name = None
            series_number = None
            if metadata:
                series_name = metadata.get("seriesName")
                series_number = metadata.get("seriesNumber")

            books.append(BookSummary(
                id=b["id"],
                title=b.get("title", "Unknown"),
                authors=authors,
                file_name=primary.get("fileName", ""),
                file_path=primary.get("filePath", ""),
                file_type=primary.get("bookType", ""),
                library_id=b.get("libraryId", 0),
                library_name=b.get("libraryName", ""),
                read_status=b.get("readStatus", "UNSET"),
                series_name=series_name,
                series_number=series_number,
                added_on=b.get("addedOn", ""),
            ))

        return books

    def search_books(self, query: str) -> list[BookSummary]:
        response = self._request(
            "GET",
            "/api/v1/app/books/search",
            params={"q": query, "page": "0", "size": "50"},
        )
        data = response.json()
        items = data.get("content", data) if isinstance(data, dict) else data

        books = []
        for b in items:
            books.append(BookSummary(
                id=b["id"],
                title=b.get("title", "Unknown"),
                authors=b.get("authors", []) if isinstance(b.get("authors"), list) else [],
                file_name=b.get("primaryFileName", ""),
                file_path="",
                file_type=b.get("primaryFileType", ""),
                library_id=b.get("libraryId", 0),
                library_name="",
                read_status=b.get("readStatus", "UNSET"),
                series_name=b.get("seriesName"),
                series_number=b.get("seriesNumber"),
                added_on=b.get("addedOn", ""),
            ))

        return books
