import feedparser
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from utils.config_loader import load_rss_sources
from utils.logger import get_logger

logger = get_logger()


def _get_entry_value(entry, name):
    """Read a feed entry field that may be an attribute or a dict key."""
    value = getattr(entry, name, None)
    if value is None and hasattr(entry, "get"):
        value = entry.get(name)
    return value


def _parse_published_datetime(entry):
    """Return (datetime, ISO-8601 string) for an entry, or (None, '')."""
    # Feedparser parsed tuples are UTC.
    for attr in ("published_parsed", "updated_parsed"):
        value = _get_entry_value(entry, attr)
        if value:
            try:
                dt = datetime(*value[:6], tzinfo=timezone.utc)
                return dt, dt.isoformat()
            except Exception:
                pass

    # Raw date strings (RFC 822 or ISO).
    for attr in ("published", "updated"):
        raw = _get_entry_value(entry, attr)
        if raw:
            raw = str(raw).strip()
            if raw:
                try:
                    dt = parsedate_to_datetime(raw)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt, dt.isoformat()
                except Exception:
                    pass
                try:
                    iso = raw
                    if iso.endswith("Z"):
                        iso = iso[:-1] + "+00:00"
                    dt = datetime.fromisoformat(iso)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt, dt.isoformat()
                except Exception:
                    pass

    return None, ""


def _entry_to_news(entry, source_name, fetched_at):
    published_raw = _get_entry_value(entry, "published") or _get_entry_value(entry, "updated") or ""
    published_dt, published_at = _parse_published_datetime(entry)

    return {
        "source": source_name,
        "title": str(_get_entry_value(entry, "title") or "").strip(),
        "summary": str(_get_entry_value(entry, "summary") or "").strip(),
        "link": str(_get_entry_value(entry, "link") or "").strip(),
        "published": str(published_raw).strip(),
        "published_at": published_at,
        "fetched_at": fetched_at,
    }


def fetch_news(limit_per_source=10):
    all_news = []
    fetched_at = datetime.now(timezone.utc).isoformat()
    sources = load_rss_sources()

    logger.info(f"{len(sources)} RSS kaynağı yükleniyor")
    print("Yüklenen kaynaklar:")
    print(sources)

    for source in sources:
        source_name = source.get("name", "Bilinmeyen")
        source_url = source.get("url", "").strip()

        if not source_url:
            logger.warning(f"Kaynak URL'si eksik: {source_name}")
            continue

        try:
            logger.info(f"RSS çekiliyor: {source_name}")
            feed = feedparser.parse(source_url)
            logger.info(f"RSS tamamlandı: {source_name}")
        except Exception as e:
            logger.error(f"RSS çekilemedi {source_name}: {e}")
            continue

        if feed.get("bozo"):
            bozo_exception = feed.get("bozo_exception")
            logger.warning(f"RSS bozuk/bozuk olabilir {source_name}: {bozo_exception}")

        if hasattr(feed, "get"):
            entries = feed.get("entries", []) or []
        else:
            entries = getattr(feed, "entries", []) or []
        print(source_name, len(entries))

        if not entries:
            logger.warning(f"RSS kaynağı boş döndü: {source_name}")
            continue

        for entry in entries[:limit_per_source]:
            try:
                all_news.append(_entry_to_news(entry, source_name, fetched_at))
            except Exception as e:
                logger.error(f"Haber işlenirken hata {source_name}: {e}")

    return all_news
