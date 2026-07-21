from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path

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
    ) -> tuple[bool, str]:
        data = {
            "savepath": save_path,
            "tags": tags,
            "paused": "true" if paused else "false",
        }
        if urls:
            data["urls"] = urls

        try:
            logger.info("Adding torrent via URL: %s", urls)
            resp = self._request("POST", "/api/v2/torrents/add", data=data)
            if resp.status_code == 200:
                return True, ""
            logger.warning("qBittorrent returned %s for URL add, falling back to file upload", resp.status_code)
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 409:
                logger.error("Failed to add torrent (HTTP %s): %s", e.response.status_code, e)
                return False, f"Error HTTP {e.response.status_code}"
        except Exception as e:
            logger.error("Failed to add torrent: %s", e)
            return False, str(e)

        logger.info("Falling back to file upload for: %s", urls)
        fallback_ok, fallback_err = self._add_torrent_via_file_upload(urls, save_path, tags, paused)
        if fallback_ok:
            return True, ""
        return False, fallback_err or "No se pudo descargar el archivo torrent desde la URL"

    def _send_magnet_to_qbit(self, magnet: str, save_path: str, tags: str, paused: bool) -> tuple[bool, str]:
        data = {
            "savepath": save_path,
            "tags": tags,
            "paused": "true" if paused else "false",
            "urls": magnet,
        }
        session = self._get_session()
        url = f"{self.base_url}/api/v2/torrents/add"
        headers = {"Referer": self.base_url}
        response = session.post(url, data=data, headers=headers)
        if response.status_code == 403:
            self._login()
            response = session.post(url, data=data, headers=headers)
        response.raise_for_status()
        return True, ""

    def _add_torrent_via_file_upload(
        self,
        urls: str,
        save_path: str,
        tags: str,
        paused: bool,
    ) -> tuple[bool, str]:
        if not urls.startswith(("http://", "https://")):
            return False, "La URL no es accesible para descarga directa"

        try:
            logger.info("Fallback: downloading from %s", urls)
            resp = httpx.get(urls, timeout=30, follow_redirects=False)

            if resp.status_code in (301, 302, 303, 307, 308):
                location = resp.headers.get("location", "")
                if location.startswith("magnet:"):
                    logger.info("Fallback: redirect to magnet link")
                    return self._send_magnet_to_qbit(location, save_path, tags, paused)

            resp.raise_for_status()
            content = resp.content
            text = content.decode("utf-8", errors="replace").strip()

            if text.startswith("magnet:"):
                logger.info("Fallback: URL returned a magnet link, passing to qBittorrent")
                return self._send_magnet_to_qbit(text, save_path, tags, paused)

            magnet_idx = text.find("magnet:")
            if magnet_idx != -1:
                magnet = text[magnet_idx:].split()[0]
                logger.info("Fallback: extracted magnet link from response")
                return self._send_magnet_to_qbit(magnet, save_path, tags, paused)

            if not content or len(content) < 20:
                return False, "El archivo torrent descargado está vacío o es demasiado pequeño"

            suffix = ".torrent"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(content)
                tmp_path = Path(tmp.name)

            logger.info("Fallback: uploading .torrent file (%d bytes) to qBittorrent", len(content))
            session = self._get_session()
            url = f"{self.base_url}/api/v2/torrents/add"
            headers = {"Referer": self.base_url}
            form_data = {
                "savepath": save_path,
                "tags": tags,
                "paused": "true" if paused else "false",
            }
            with open(tmp_path, "rb") as f:
                files = {"torrents": (tmp_path.name, f, "application/x-bittorrent")}
                response = session.post(url, data=form_data, files=files, headers=headers)
                if response.status_code == 403:
                    self._login()
                    response = session.post(url, data=form_data, files=files, headers=headers)
            tmp_path.unlink(missing_ok=True)
            response.raise_for_status()
            logger.info("Fallback: torrent uploaded successfully via file")
            return True, ""
        except httpx.HTTPStatusError as e:
            logger.error("Fallback file upload failed (HTTP %s): %s", e.response.status_code, e)
            return False, f"Error subiendo el archivo torrent: HTTP {e.response.status_code}"
        except Exception as e:
            logger.error("Fallback file upload failed: %s", e)
            return False, f"Error descargando/subiendo torrent: {e}"

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
