from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass
class TorrentInfo:
    hash: str
    name: str
    save_path: str
    state: str
    progress: float
    dlspeed: int
    upspeed: int
    ratio: float
    num_seeds: int
    size: int
    content_path: str


class QBitClient:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self._session: httpx.Client | None = None

    def _get_session(self) -> httpx.Client:
        if self._session is None:
            self._session = httpx.Client(timeout=15)
            self._login()
        return self._session

    def _login(self) -> None:
        url = f"{self.base_url}/api/v2/auth/login"
        data = {"username": self.username, "password": self.password}
        headers = {"Referer": self.base_url}

        try:
            response = self._session.post(url, data=data, headers=headers)
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("qBittorrent login failed: %s", e)
            self._session = None
            raise

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        session = self._get_session()
        url = f"{self.base_url}{path}"
        headers = kwargs.pop("headers", {})
        headers.setdefault("Referer", self.base_url)

        try:
            response = session.request(method, url, headers=headers, **kwargs)
            if response.status_code == 403:
                self._login()
                response = session.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()
            return response
        except httpx.HTTPError:
            self._session = None
            raise

    def test_connection(self) -> tuple[bool, str]:
        try:
            resp = self._request("GET", "/api/v2/app/version")
            return True, f"Conectado (v{resp.text})"
        except Exception as e:
            return False, str(e)

    def get_torrents(self, category: str | None = None) -> list[TorrentInfo]:
        params = {}
        if category:
            params["category"] = category

        response = self._request("GET", "/api/v2/torrents/info", params=params)
        data = response.json()

        return [
            TorrentInfo(
                hash=t["hash"],
                name=t["name"],
                save_path=t["save_path"],
                state=t["state"],
                progress=t["progress"],
                dlspeed=t["dlspeed"],
                upspeed=t["upspeed"],
                ratio=t.get("ratio", 0),
                num_seeds=t.get("num_seeds", 0),
                size=t["size"],
                content_path=t.get("content_path", ""),
            )
            for t in data
        ]

    def get_torrent_files(self, torrent_hash: str) -> list[dict]:
        response = self._request("GET", "/api/v2/torrents/files", params={"hash": torrent_hash})
        return response.json()

    def add_torrent(
        self,
        urls: str = "",
        save_path: str = "/bookdrop",
        tags: str = "grimmory",
        paused: bool = False,
    ) -> bool:
        data = {
            "savepath": save_path,
            "tags": tags,
            "paused": "true" if paused else "false",
        }
        if urls:
            data["urls"] = urls

        try:
            self._request("POST", "/api/v2/torrents/add", data=data)
            return True
        except Exception as e:
            logger.error("Failed to add torrent: %s", e)
            return False

    def delete_torrent(self, torrent_hash: str, delete_files: bool = False) -> bool:
        data = {
            "hashes": torrent_hash,
            "deleteFiles": "true" if delete_files else "false",
        }
        try:
            self._request("POST", "/api/v2/torrents/delete", data=data)
            return True
        except Exception as e:
            logger.error("Failed to delete torrent: %s", e)
            return False

    def pause_torrent(self, torrent_hash: str) -> bool:
        data = {"hashes": torrent_hash}
        try:
            self._request("POST", "/api/v2/torrents/pause", data=data)
            return True
        except Exception as e:
            logger.error("Failed to pause torrent: %s", e)
            return False

    def resume_torrent(self, torrent_hash: str) -> bool:
        data = {"hashes": torrent_hash}
        try:
            self._request("POST", "/api/v2/torrents/resume", data=data)
            return True
        except Exception as e:
            logger.error("Failed to resume torrent: %s", e)
            return False

    def set_location(self, torrent_hashes: str, location: str) -> bool:
        data = {"hashes": torrent_hashes, "location": location}
        try:
            self._request("POST", "/api/v2/torrents/set_location", data=data)
            return True
        except Exception as e:
            logger.error("Failed to set location: %s", e)
            return False

    def recheck(self, torrent_hashes: str) -> bool:
        data = {"hashes": torrent_hashes}
        try:
            self._request("POST", "/api/v2/torrents/recheck", data=data)
            return True
        except Exception as e:
            logger.error("Failed to recheck: %s", e)
            return False
