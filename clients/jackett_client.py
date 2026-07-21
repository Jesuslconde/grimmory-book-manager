from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx
from lxml import etree

logger = logging.getLogger(__name__)

NAMESPACES = {
    "atom": "http://www.w3.org/2005/Atom",
    "torznab": "http://torznab.github.io/schemas/2015/feed",
}


@dataclass
class SearchResult:
    title: str
    download_url: str
    size_bytes: int
    seeders: int
    leechers: int
    indexer: str
    publish_date: str
    category: str


class JackettClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    @property
    def _api_base(self) -> str:
        return f"{self.base_url}/api/v2.0/indexers"

    def search(self, query: str, indexer: str = "all", category: str = "100005,100006") -> list[SearchResult]:
        url = f"{self._api_base}/{indexer}/results/torznab/api"
        params = {
            "apikey": self.api_key,
            "t": "search",
            "q": query,
            "cat": category,
            "cache": "false",
        }

        try:
            response = httpx.get(url, params=params, timeout=30)
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("Jackett search failed: %s", e)
            return []

        return self._parse_results(response.text)

    def get_indexers(self) -> list[dict[str, str]]:
        url = f"{self._api_base}/all/results/torznab/api"
        params = {"apikey": self.api_key, "t": "indexers", "configured": "true"}

        try:
            response = httpx.get(url, params=params, timeout=15)
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("Failed to get indexers: %s", e)
            return []

        return self._parse_indexers(response.text)

    def test_connection(self) -> tuple[bool, str]:
        url = f"{self._api_base}/all/results/torznab/api"
        params = {"apikey": self.api_key, "t": "caps"}

        try:
            response = httpx.get(url, params=params, timeout=10)
            response.raise_for_status()
            return True, "Conectado"
        except httpx.HTTPError as e:
            return False, str(e)

    def _parse_results(self, xml_text: str) -> list[SearchResult]:
        results = []
        try:
            root = etree.fromstring(xml_text.encode())
        except etree.XMLSyntaxError:
            logger.warning("Failed to parse Jackett XML response")
            return []

        for item in root.findall(".//atom:entry", NAMESPACES):
            title_el = item.find("atom:title", NAMESPACES)
            title = title_el.text if title_el is not None else "Unknown"

            download_url = ""
            for link in item.findall("atom:link", NAMESPACES):
                href = link.get("href", "")
                link_type = link.get("type", "")
                if "application/x-bittorrent" in link_type or href.endswith(".torrent"):
                    download_url = href
                    break
            if not download_url:
                for link in item.findall("atom:link", NAMESPACES):
                    href = link.get("href", "")
                    if href.startswith("magnet:"):
                        download_url = href
                        break
            if not download_url:
                for link in item.findall("atom:link", NAMESPACES):
                    download_url = link.get("href", "")
                    break

            size = 0
            size_el = item.find("torznab:attr[@name='size']", NAMESPACES)
            if size_el is not None:
                size = int(size_el.get("value", 0))

            seeders = 0
            seeders_el = item.find("torznab:attr[@name='seeders']", NAMESPACES)
            if seeders_el is not None:
                seeders = int(seeders_el.get("value", 0))

            leechers = 0
            leechers_el = item.find("torznab:attr[@name='peers']", NAMESPACES)
            if leechers_el is not None:
                leechers = int(leechers_el.get("value", 0))
                if seeders_el is not None:
                    leechers = max(0, leechers - seeders)

            indexer = ""
            for cat_el in item.findall("atom:category", NAMESPACES):
                cat_title = cat_el.get("title", "")
                if cat_title:
                    indexer = cat_title
                    break

            publish_date = ""
            pub_el = item.find("atom:published", NAMESPACES)
            if pub_el is None:
                pub_el = item.find("atom:updated", NAMESPACES)
            if pub_el is not None and pub_el.text:
                publish_date = pub_el.text

            category = ""
            cat_el = item.find("atom:category", NAMESPACES)
            if cat_el is not None:
                category = cat_el.get("term", "")

            if download_url:
                results.append(SearchResult(
                    title=title,
                    download_url=download_url,
                    size_bytes=size,
                    seeders=seeders,
                    leechers=leechers,
                    indexer=indexer,
                    publish_date=publish_date,
                    category=category,
                ))

        return results

    def _parse_indexers(self, xml_text: str) -> list[dict[str, str]]:
        indexers = []
        try:
            root = etree.fromstring(xml_text.encode())
        except etree.XMLSyntaxError:
            return []

        for channel in root.findall(".//atom:category", NAMESPACES):
            title = channel.get("title", "")
            indexers.append({"id": title.lower().replace(" ", ""), "name": title})

        return indexers
