from __future__ import annotations

import asyncio
import html
import re
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

CACHE_TTL = timedelta(minutes=10)
FETCH_TIMEOUT = 6
USER_AGENT = "Mozilla/5.0 (compatible; SomNLP-ResearchPlatform/1.0; +https://github.com/)"

_NS = {
    "media": "http://search.yahoo.com/mrss/",
    "content": "http://purl.org/rss/1.0/modules/content/",
}

SOURCES: dict[str, dict] = {
    "bbc": {
        "name": "BBC Somali",
        "feed_url": "https://feeds.bbci.co.uk/somali/rss.xml",
        "site_url": "https://www.bbc.com/somali",
    },
    "dalsan": {
        "name": "Radio Dalsan",
        "feed_url": "https://www.radiodalsan.com/feed/",
        "site_url": "https://www.radiodalsan.com",
    },
    "sntv": {
        "name": "SNTV",
        "feed_url": "https://www.sntv.so/feed/",
        "site_url": "https://www.sntv.so",
    },
    "caasimada": {
        "name": "Caasimada Online",
        "feed_url": "https://caasimada.net/feed/",
        "site_url": "https://caasimada.net",
    },
    "goobjoog": {
        "name": "Goobjoog News",
        "feed_url": "https://goobjoog.com/feed/",
        "site_url": "https://goobjoog.com",
    },
}

_cache: dict[str, dict] = {}

_TAG_RE = re.compile(r"<[^>]+>")
_IMG_SRC_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)


def _clean_text(raw: str | None, max_len: int = 220) -> str:
    if not raw:
        return ""
    text = _TAG_RE.sub(" ", raw)
    text = html.unescape(text)
    text = " ".join(text.split())
    if len(text) > max_len:
        text = text[:max_len].rsplit(" ", 1)[0] + "…"
    return text


def _parse_pubdate(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except (TypeError, ValueError):
        return None


def _extract_thumbnail(item: ElementTree.Element) -> str | None:
    media_thumb = item.find("media:thumbnail", _NS)
    if media_thumb is not None and media_thumb.get("url"):
        return media_thumb.get("url")

    enclosure = item.find("enclosure")
    if enclosure is not None and (enclosure.get("type") or "").startswith("image") and enclosure.get("url"):
        return enclosure.get("url")

    content_encoded = item.find("content:encoded", _NS)
    if content_encoded is not None and content_encoded.text:
        m = _IMG_SRC_RE.search(content_encoded.text)
        if m:
            return m.group(1)

    description = item.find("description")
    if description is not None and description.text:
        m = _IMG_SRC_RE.search(description.text)
        if m:
            return m.group(1)

    return None


def _parse_rss(xml_bytes: bytes, source_name: str) -> list[dict]:
    root = ElementTree.fromstring(xml_bytes)
    items = root.findall(".//item")
    parsed: list[dict] = []
    for item in items:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not title or not link:
            continue
        parsed.append({
            "title": html.unescape(title),
            "link": link,
            "description": _clean_text(item.findtext("description")),
            "published_at": _parse_pubdate(item.findtext("pubDate")),
            "thumbnail": _extract_thumbnail(item),
            "source_name": source_name,
        })
    return parsed


def _fetch_source_sync(source_id: str) -> list[dict]:
    source = SOURCES[source_id]
    req = urllib.request.Request(source["feed_url"], headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
        raw = resp.read()
    return _parse_rss(raw, source["name"])


async def get_source(source_id: str, limit: int, force: bool = False) -> dict:
    source = SOURCES[source_id]
    cached = _cache.get(source_id)
    is_fresh = cached is not None and datetime.now(timezone.utc) - cached["fetched_at"] < CACHE_TTL

    if is_fresh and not force:
        items = cached["items"]
        error = None
    else:
        try:
            items = await asyncio.to_thread(_fetch_source_sync, source_id)
            _cache[source_id] = {"items": items, "fetched_at": datetime.now(timezone.utc)}
            error = None
        except (urllib.error.URLError, ElementTree.ParseError, TimeoutError, OSError) as exc:
            if cached is not None:
                items = cached["items"]
                error = f"Live refresh failed ({exc}); showing last cached results."
            else:
                items = []
                error = f"Unable to reach {source['name']} right now."

    return {
        "source": source_id,
        "name": source["name"],
        "site_url": source["site_url"],
        "fetched_at": (_cache.get(source_id) or {}).get("fetched_at", datetime.now(timezone.utc)).isoformat(),
        "error": error,
        "items": items[:limit],
    }
