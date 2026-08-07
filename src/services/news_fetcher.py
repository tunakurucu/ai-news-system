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


def _is_valid_entry(item):
    """Require a title and an article URL; timestamp is captured when available."""
    return bool(item.get("title")) and bool(item.get("link"))


def _is_source_enabled(source):
    """Backwards-compatible enabled check: default to True when missing."""
    return bool(source.get("enabled", True))


def _count_valid(entries, source_name, fetched_at, limit):
    """Convert raw entries to normalized items and skip invalid ones."""
    valid = []
    skipped = 0
    for entry in entries[:limit]:
        try:
            item = _entry_to_news(entry, source_name, fetched_at)
        except Exception as e:
            logger.error(f"Haber işlenirken hata {source_name}: {e}")
            skipped += 1
            continue

        if _is_valid_entry(item):
            valid.append(item)
        else:
            skipped += 1
            logger.warning(f"Geçersiz haber atlanıyor {source_name}: title={bool(item.get('title'))}, link={bool(item.get('link'))}")

    return valid, skipped


def fetch_news(limit_per_source=10):
    """Fetch, normalize, and validate news from configured RSS sources.

    Prints a lightweight source-health summary after the run:
      - OK: source returned one or more entries
      - ZERO: source responded but returned no entries
      - FAILED: source could not be reached or parsed
      - DISABLED: source is marked enabled=false
    """
    all_news = []
    fetched_at = datetime.now(timezone.utc).isoformat()
    sources = load_rss_sources()

    logger.info(f"{len(sources)} RSS kaynağı yükleniyor")
    print("Yüklenen kaynaklar:")
    print(sources)

    source_results = []

    for source in sources:
        source_name = source.get("name", "Bilinmeyen")
        source_url = source.get("url", "").strip()

        if not _is_source_enabled(source):
            message = f"{source_name}: DISABLED"
            logger.info(message)
            source_results.append({"source": source_name, "status": "disabled", "count": 0})
            print(message)
            continue

        if not source_url:
            message = f"{source_name}: FAILED (kaynak URL'si eksik)"
            logger.warning(message)
            source_results.append({"source": source_name, "status": "failed", "count": 0})
            print(message)
            continue

        feed = None
        try:
            logger.info(f"RSS çekiliyor: {source_name}")
            feed = feedparser.parse(source_url)
            logger.info(f"RSS tamamlandı: {source_name}")
        except Exception as e:
            message = f"{source_name}: FAILED ({e})"
            logger.error(message)
            source_results.append({"source": source_name, "status": "failed", "count": 0})
            print(message)
            continue

        if feed.get("bozo"):
            bozo_exception = feed.get("bozo_exception")
            logger.warning(f"RSS bozuk/bozuk olabilir {source_name}: {bozo_exception}")

        if hasattr(feed, "get"):
            entries = feed.get("entries", []) or []
        else:
            entries = getattr(feed, "entries", []) or []

        if not entries:
            message = f"{source_name}: ZERO (0 geçerli haber)"
            logger.warning(f"RSS kaynağı boş döndü: {source_name}")
            source_results.append({"source": source_name, "status": "zero", "count": 0})
            print(message)
            continue

        valid_items, skipped = _count_valid(entries, source_name, fetched_at, limit_per_source)
        all_news.extend(valid_items)

        total_in_feed = len(entries)
        returned = len(valid_items)
        message = f"{source_name}: OK ({returned}/{limit_per_source} haber, kaynakta {total_in_feed} kayıt)"
        logger.info(message)
        source_results.append({"source": source_name, "status": "ok", "count": returned})
        print(message)

    # Attach the health summary for callers/tests that want to inspect it.
    fetch_news.source_results = source_results

    print("\n--- KAYNAK SAĞLIK ÖZETİ ---")
    for result in source_results:
        status_label = result["status"].upper()
        print(f"{result['source']}: {status_label} ({result['count']} haber)")

    return all_news
