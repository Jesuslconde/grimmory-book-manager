from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx
from lxml import etree

logger = logging.getLogger(__name__)

NAMESPACES = {
    "atom": "http://www.w3.org/2005/Atom",
    "torznab": "http://torznab.com/schemas/2015/feed",
    "jackett": "https://jackett.com/xmlns",
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

    def search(self, query: str, indexer: str = "epublibre", category: str = "7000,7020") -> list[SearchResult]:
        url = f"{self._api_base}/{indexer}/results/torznab/api"
        params = {
            "apikey": self.api_key,
            "t": "search",
            "q": query,
        }
        if category:
            params["cat"] = category
        params["cache"] = "false"

        logger.info("Jackett search: GET %s params=%s", url, {k: v for k, v in params.items() if k != "apikey"})

        try:
            response = httpx.get(url, params=params, timeout=30)
            logger.info("Jackett response: %d (%d bytes)", response.status_code, len(response.text))
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("Jackett search failed: %s", e)
            return []

        logger.debug("Jackett XML (first 2000 chars): %s", response.text[:2000])
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
        except etree.XMLSyntaxError as e:
            logger.error("Failed to parse Jackett XML: %s", e)
            logger.error("XML text (first 1000): %s", xml_text[:1000])
            return []

        items = root.findall(".//item")
        logger.info("Found %d items in XML", len(items))

        for item in items:
            title_el = item.find("title")
            title = title_el.text if title_el is not None and title_el.text else "Unknown"

            http_torrent_url = ""
            magnet_url = ""
            any_http_url = ""

            for enclosure in item.findall("enclosure"):
                enc_url = enclosure.get("url", "")
                enc_type = enclosure.get("type", "")
                if enc_url.startswith("magnet:"):
                    if not magnet_url:
                        magnet_url = enc_url
                elif enc_url.startswith(("http://", "https://")):
                    if "application/x-bittorrent" in enc_type or enc_url.endswith(".torrent"):
                        if not http_torrent_url:
                            http_torrent_url = enc_url
                    elif not any_http_url:
                        any_http_url = enc_url

            for link in item.findall("link"):
                href = link.text.strip() if link.text else ""
                if href.startswith("magnet:"):
                    if not magnet_url:
                        magnet_url = href
                elif href.startswith(("http://", "https://")):
                    if not any_http_url:
                        any_http_url = href

            download_url = http_torrent_url or any_http_url or magnet_url

            size = 0
            size_el = item.find("size")
            if size_el is not None and size_el.text:
                try:
                    size = int(size_el.text)
                except ValueError:
                    pass
            if not size:
                size_el = item.find("torznab:attr[@name='size']", NAMESPACES)
                if size_el is not None:
                    try:
                        size = int(size_el.get("value", 0))
                    except ValueError:
                        pass

            seeders = 0
            seeders_el = item.find("torznab:attr[@name='seeders']", NAMESPACES)
            if seeders_el is not None:
                try:
                    seeders = int(seeders_el.get("value", 0))
                except ValueError:
                    pass

            leechers = 0
            leechers_el = item.find("torznab:attr[@name='peers']", NAMESPACES)
            if leechers_el is not None:
                try:
                    leechers = int(leechers_el.get("value", 0))
                except ValueError:
                    pass
                leechers = max(0, leechers - seeders)

            indexer = ""
            jackett_indexer = item.find("jackettindexer")
            if jackett_indexer is not None and jackett_indexer.text:
                indexer = jackett_indexer.text
            if not indexer:
                attr_el = item.find("torznab:attr[@name='indexer']", NAMESPACES)
                if attr_el is not None:
                    indexer = attr_el.get("value", "")

            publish_date = ""
            pub_el = item.find("pubDate")
            if pub_el is not None and pub_el.text:
                publish_date = pub_el.text

            category = ""
            cat_el = item.find("category")
            if cat_el is not None:
                category = cat_el.text or ""
            if not category:
                attr_el = item.find("torznab:attr[@name='category']", NAMESPACES)
                if attr_el is not None:
                    category = attr_el.get("value", "")

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
            else:
                logger.warning("Skipping result '%s': no download URL found", title)

        logger.info("Parsed %d results (of %d items)", len(results), len(items))
        return results

    def _parse_indexers(self, xml_text: str) -> list[dict[str, str]]:
        indexers = []
        try:
            root = etree.fromstring(xml_text.encode())
        except etree.XMLSyntaxError:
            return []

        seen = set()
        for channel in root.findall(".//atom:category", NAMESPACES):
            title = channel.get("title", "")
            if title and title not in seen:
                seen.add(title)
                indexers.append({"id": title.lower().replace(" ", ""), "name": title})

        for cat_el in root.findall(".//category"):
            title = cat_el.get("title", "")
            if title and title not in seen:
                seen.add(title)
                indexers.append({"id": title.lower().replace(" ", ""), "name": title})

        return indexers
