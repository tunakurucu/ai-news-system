import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

_TURKISH_MONTHS = [
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"
]

_DEFAULT_HERO_LEAD = (
    "RSS kaynaklarından derlenen günün en önemli haberleri. "
    "Kaynakları ve yayınlanma zamanlarını açık biçimde görebilirsiniz."
)

_CATEGORIES = [
    ("all", "Tümü"),
    ("ekonomi", "Ekonomi"),
    ("teknoloji", "Teknoloji"),
    ("dünya", "Dünya"),
    ("gümrük", "Gümrük"),
    ("spor", "Spor"),
    ("genel", "Genel"),
]


_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _escape(value):
    """Escape source-controlled text for safe HTML insertion."""
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def _format_published(item):
    """Format a Turkish publication date like '7 Ağustos 2026, 17:32'."""
    raw = item.get("published_at") or item.get("published") or ""
    raw = str(raw).strip()
    if not raw:
        return ""

    dt = None
    try:
        iso = raw
        if iso.endswith("Z"):
            iso = iso[:-1] + "+00:00"
        dt = datetime.fromisoformat(iso)
    except Exception:
        pass

    if dt is None:
        try:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(raw)
        except Exception:
            pass

    if dt is None:
        return ""

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    try:
        dt = dt.astimezone(ZoneInfo("Europe/Istanbul"))
    except Exception:
        pass

    return f"{dt.day} {_TURKISH_MONTHS[dt.month - 1]} {dt.year}, {dt.hour:02d}:{dt.minute:02d}"


def _format_today():
    """Return today's date in Turkish, e.g. '7 Ağustos 2026'."""
    try:
        dt = datetime.now(ZoneInfo("Europe/Istanbul"))
    except Exception:
        dt = datetime.now()
    return f"{dt.day} {_TURKISH_MONTHS[dt.month - 1]} {dt.year}"


def _format_date_tr(dt):
    """Format an existing datetime as a Turkish date."""
    return f"{dt.day} {_TURKISH_MONTHS[dt.month - 1]} {dt.year}"


def _format_iso_date(date_text):
    """Format YYYY-MM-DD as a Turkish date."""
    try:
        dt = datetime.strptime(date_text, "%Y-%m-%d")
    except Exception:
        return _escape(date_text)
    return _format_date_tr(dt)


def _meta_line(item):
    """Build 'Source · date' metadata, falling back to source only."""
    source = _escape(item.get("source", ""))
    date = _format_published(item)
    if date:
        return f"{source} · {date}"
    return source


def _page(title, body, active=None):
    """Wrap a page in the shared shell."""
    nav_links = [
        ("index.html", "Güncel", "index"),
        ("archive.html", "Arşiv", "archive"),
        ("search.html", "Arama", "search"),
    ]
    nav_items = []
    for href, label, key in nav_links:
        cls = ' class="active"' if active == key else ""
        nav_items.append(f'<a href="{_escape(href)}"{cls}>{_escape(label)}</a>')

    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{_escape(title)}</title>
    <link rel="stylesheet" href="assets/css/news.css">
    <script src="assets/js/news.js" defer></script>
</head>
<body>
    <header class="site-header">
        <div class="header-inner">
            <a class="brand" href="index.html">AI News</a>
            <button class="menu-toggle" aria-label="Menü" aria-expanded="false">
                <span></span>
                <span></span>
                <span></span>
            </button>
            <nav class="nav-links">
                {"".join(nav_items)}
            </nav>
            <div class="header-date">{_format_today()}</div>
        </div>
    </header>

    {body}

    <footer class="site-footer">
        <div class="footer-inner">
            <div>AI News — Otomatik olarak oluşturulur</div>
            <div class="footer-links">
                <a href="rss_sources.json">RSS Kaynakları</a>
                <a href="https://github.com/tunakurucu/ai-news-system">GitHub</a>
            </div>
        </div>
    </footer>
</body>
</html>
"""


def _news_item(item, compact=False):
    """Render a feed-style article item."""
    search_text = re.sub(
        r"\s+",
        " ",
        " ".join([
            str(item.get("title", "")),
            str(item.get("summary", "")),
            str(item.get("category", "")),
            str(item.get("source", "")),
        ]).lower()
    ).strip()

    category = _escape(item.get("category", "genel").upper())
    title = _escape(item.get("title", ""))
    summary = _escape(item.get("summary", ""))
    meta = _meta_line(item)
    link = (item.get("link") or "").strip() or "#"
    compact_cls = " news-card-compact" if compact else ""

    return f"""<article class="news-card{compact_cls}" data-search="{_escape(search_text)}" data-category="{_escape(item.get('category', 'genel'))}">
    <div class="news-card-body">
        <div class="eyebrow-row">
            <span class="category-label">{category}</span>
            <span class="source source-inline">{meta}</span>
        </div>
        <h3>{title}</h3>
        <p>{summary}</p>
    </div>
    <div class="card-footer">
        <span class="source source-block">{meta}</span>
        <a class="read-link" href="{_escape(link)}" target="_blank" rel="noopener noreferrer">Haberi oku</a>
    </div>
</article>
"""


def _stats_html(stats):
    """Render a compact editorial stats line."""
    if not stats:
        return ""
    items = []
    for key, value in stats.items():
        if key == "generated_at":
            continue
        label = _escape(key.replace("_", " "))
        items.append(
            f'<span class="stat-item"><strong>{label}</strong> {_escape(value)}</span>'
        )
    if not items:
        return ""
    return (
        '<div class="stats-bar" aria-label="Günlük istatistikler">'
        f'{"".join(items)}</div>\n'
    )


def _featured_html(top_news):
    """Render the daily briefing section."""
    if not top_news:
        return '<p class="empty-state">Bugün için öne çıkan haber bulunamadı.</p>'
    lead = top_news[0]
    remaining = top_news[1:5]

    lead_meta = _meta_line(lead)
    lead_summary = _escape(lead.get("summary", ""))
    lead_title = _escape(lead.get("title", ""))
    lead_link = _escape((lead.get("link") or "").strip() or "#")
    lead_category = _escape(lead.get("category", "genel").upper())

    if remaining:
        items = []
        for index, item in enumerate(remaining, start=2):
            items.append(
                f"""<li class="briefing-item">
    <article>
        <div class="briefing-rank" aria-hidden="true">{index}</div>
        <div class="briefing-copy">
            <div class="eyebrow-row">
                <span class="category-label">{_escape(item.get("category", "genel").upper())}</span>
                <span class="source">{_meta_line(item)}</span>
            </div>
            <h3>{_escape(item.get("title", ""))}</h3>
            <p>{_escape(item.get("summary", ""))}</p>
            <a class="read-link" href="{_escape((item.get("link") or "").strip() or "#")}" target="_blank" rel="noopener noreferrer">Haberi oku</a>
        </div>
    </article>
</li>"""
            )
        side_html = f'<ol class="briefing-list">{"".join(items)}</ol>'
    else:
        side_html = '<p class="empty-state">Daha fazla öne çıkan haber bulunmuyor.</p>'

    return f"""<section class="briefing-shell" aria-label="Bugünün özeti">
    <article class="briefing-lead">
        <div class="eyebrow-row">
            <span class="briefing-kicker">1 numaralı gelişme</span>
            <span class="category-label">{lead_category}</span>
        </div>
        <h3>{lead_title}</h3>
        <p>{lead_summary}</p>
        <div class="card-footer">
            <span class="source">{lead_meta}</span>
            <a class="read-link" href="{lead_link}" target="_blank" rel="noopener noreferrer">Haberi oku</a>
        </div>
    </article>
    <aside class="briefing-side">
        <h3 class="briefing-side-title">Hızlı bakış</h3>
        {side_html}
    </aside>
</section>
"""


def _category_sections_html(grouped_news):
    """Render grouped news cards by category."""
    sections = []
    for category, items in grouped_news.items():
        cards = "".join([_news_item(item) for item in items])
        sections.append(
            f"""<section class="category-section">
    <div class="category-heading">
        <h2 class="category-title">{_escape(category.upper())}</h2>
        <p class="category-count">{len(items)} haber</p>
    </div>
    <div class="news-list">
        {cards}
    </div>
</section>
"""
        )
    return "".join(sections)


def _category_filter_buttons():
    """Render the category filter pill bar."""
    buttons = []
    for key, label in _CATEGORIES:
        active = " active" if key == "all" else ""
        buttons.append(
            f'<button class="category-filter-btn{active}" data-category="{_escape(key)}">{_escape(label)}</button>'
        )
    return "".join(buttons)


def _search_box(input_id, placeholder):
    return f"""<div class="search-box">
    <span class="search-icon" aria-hidden="true">Ara</span>
    <input type="text" id="{input_id}" placeholder="{_escape(placeholder)}" autocomplete="off">
</div>
"""


def generate_news_html(news_items, stats, page_heading="Bugünün Haberleri", hero_date=None, hero_lead=None):
    """Generate the redesigned homepage or a dated daily page."""
    top_news = sorted(
        news_items,
        key=lambda x: x.get("importance_score", 0),
        reverse=True
    )[:5]

    grouped_news = {}
    for item in news_items:
        category = item.get("category", "genel")
        grouped_news.setdefault(category, []).append(item)

    if hero_date:
        display_date = _format_iso_date(hero_date)
    else:
        display_date = _format_today()
    lead_text = hero_lead or _DEFAULT_HERO_LEAD

    body = f"""<main class="site-wrapper">
    <section class="hero">
        <div class="hero-text">
            <h1>{_escape(page_heading)}</h1>
            <p class="hero-date">{_escape(display_date)}</p>
            <p class="hero-lead">{_escape(lead_text)}</p>
        </div>
        {_search_box('home-search-input', 'Güncel haberlerde ara...')}
        <div class="category-filters">
            {_category_filter_buttons()}
        </div>
        {_stats_html(stats)}
    </section>

    <section class="section">
        <h2 class="section-title">Bugünün Özeti</h2>
        <p class="section-intro">Gün içindeki en yüksek önem puanlı gelişmeleri hızlıca kavrayın.</p>
        {_featured_html(top_news)}
    </section>

    {_category_sections_html(grouped_news)}
</main>
"""

    return _page(page_heading, body, active="index")


def generate_search_html(search_index=None):
    """Generate the search page with embedded search data."""
    data_json = "[]"
    if search_index is not None:
        raw = json.dumps(search_index, ensure_ascii=False)
        # Prevent a closing </script> tag inside the JSON.
        raw = raw.replace("</script>", "<\\/script>")
        raw = raw.replace("</SCRIPT>", "<\\/SCRIPT>")
        data_json = raw

    body = f"""<main class="site-wrapper">
    <section class="hero hero-small">
        <h1>Haber Arama</h1>
        <p class="hero-lead">Başlık, özet, kategori veya kaynağa göre arayın. Sonuçlar ana akıştaki aynı okunabilir düzenle listelenir.</p>
        {_search_box('search-input', 'Başlık, konu, kategori veya kaynak ara...')}
    </section>

    <div class="results-toolbar">
        <p id="search-results-meta" class="results-meta" aria-live="polite"></p>
    </div>
    <div id="search-results"></div>

    <script type="application/json" id="search-data">{data_json}</script>
</main>
"""

    return _page("Haber Arama", body, active="search")


def generate_archive_html(project_root):
    """Generate the archive page listing past daily news files."""
    raw_folder = Path(project_root) / "data" / "raw"
    archive_files = []

    for file in raw_folder.glob("*-news.json"):
        if file.name == "latest-news.json":
            continue
        archive_files.append(file)

    archive_files.sort(reverse=True)

    groups = {}
    for file in archive_files:
        date_name = file.stem.replace("-news", "")
        try:
            dt = datetime.strptime(date_name, "%Y-%m-%d")
            display = _format_date_tr(dt)
            group_label = f"{_TURKISH_MONTHS[dt.month - 1]} {dt.year}"
        except Exception:
            display = _escape(date_name)
            group_label = "Arşiv"

        href = f"{date_name}-news.html"
        groups.setdefault(group_label, []).append(
            f"""<li class="archive-entry">
    <a href="{_escape(href)}">
        <span class="archive-date">{_escape(display)}</span>
        <span class="archive-arrow" aria-hidden="true">›</span>
    </a>
</li>"""
        )

    if not groups:
        grid = '<p class="empty-state">Henüz arşivlenmiş haber bulunmuyor.</p>'
    else:
        sections = []
        for label, items in groups.items():
            sections.append(
                f"""<section class="archive-group">
    <h2 class="archive-group-title">{_escape(label)}</h2>
    <ul class="archive-list">
        {"".join(items)}
    </ul>
</section>"""
            )
        grid = "".join(sections)

    body = f"""<main class="site-wrapper">
    <section class="hero hero-small">
        <h1>Haber Arşivi</h1>
        <p class="hero-lead">Geçmiş günleri tarih sırasıyla tarayın. Her tarih aynı güncel tasarımla oluşturulmuş günlük sayfaya gider.</p>
    </section>
    {grid}
</main>
"""

    return _page("Haber Arşivi", body, active="archive")


def get_css():
    """Return the shared site stylesheet."""
    return """:root {
    --bg: #f3f1ec;
    --card: #FFFFFF;
    --primary: #1f4db8;
    --primary-hover: #173f98;
    --border: #d9d3c7;
    --border-strong: #bbb2a2;
    --text: #181818;
    --muted: #5f5a52;
    --muted-strong: #413b34;
    --surface: #f8f6f1;
    --max-width: 1180px;
    --reading-width: 760px;
    --radius: 10px;
}

* {
    box-sizing: border-box;
}

html {
    scroll-behavior: smooth;
}

body {
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    -webkit-font-smoothing: antialiased;
    line-height: 1.6;
    min-height: 100vh;
}

a {
    color: inherit;
    text-decoration: none;
}

a:hover {
    color: inherit;
}

a:focus-visible,
button:focus-visible,
input:focus-visible {
    outline: 3px solid rgba(31, 77, 184, 0.22);
    outline-offset: 2px;
}

.site-wrapper,
.header-inner,
.footer-inner {
    max-width: var(--max-width);
    margin: 0 auto;
    padding: 0 24px;
}

/* Header */
.site-header {
    position: sticky;
    top: 0;
    z-index: 50;
    background: rgba(248, 246, 241, 0.96);
    backdrop-filter: blur(12px);
    border-bottom: 1px solid var(--border);
}

.header-inner {
    display: flex;
    align-items: center;
    gap: 16px;
    padding-top: 12px;
    padding-bottom: 12px;
    min-height: 64px;
}

.brand {
    font-size: 20px;
    font-weight: 750;
    letter-spacing: -0.01em;
    color: var(--text);
    margin-right: auto;
}

.brand:hover {
    color: var(--text);
}

.nav-links {
    display: flex;
    align-items: center;
    gap: 6px;
}

.nav-links a {
    color: var(--muted);
    font-weight: 600;
    padding: 8px 10px;
    border-radius: 6px;
    transition: color 0.15s, background 0.15s, border-color 0.15s;
    border-bottom: 2px solid transparent;
}

.nav-links a:hover,
.nav-links a.active {
    color: var(--primary);
    background: rgba(31, 77, 184, 0.06);
    border-bottom-color: rgba(31, 77, 184, 0.35);
}

.header-date {
    color: var(--muted);
    font-size: 14px;
    font-weight: 500;
    white-space: nowrap;
}

.menu-toggle {
    display: none;
    background: none;
    border: none;
    cursor: pointer;
    flex-direction: column;
    gap: 5px;
    padding: 6px;
}

.menu-toggle span {
    display: block;
    width: 22px;
    height: 2px;
    background: var(--text);
    border-radius: 2px;
}

/* Hero */
.hero {
    padding: 42px 0 18px;
}

.hero-small {
    padding: 34px 0 10px;
}

.hero h1 {
    font-size: 54px;
    font-weight: 780;
    letter-spacing: -0.03em;
    margin: 0 0 10px;
    line-height: 1.1;
    max-width: 12ch;
}

.hero-date {
    color: var(--muted-strong);
    font-size: 17px;
    margin: 0 0 14px;
    font-weight: 600;
}

.hero-lead {
    color: var(--muted);
    font-size: 21px;
    max-width: 720px;
    margin: 0 0 24px;
    line-height: 1.52;
}

/* Search */
.search-box {
    position: relative;
    max-width: 700px;
    margin: 0 0 18px;
}

.search-icon {
    position: absolute;
    left: 16px;
    top: 50%;
    transform: translateY(-50%);
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--muted);
    pointer-events: none;
}

.search-box input {
    width: 100%;
    padding: 16px 18px 16px 54px;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--card);
    font-size: 16px;
    color: var(--text);
    outline: none;
    transition: border-color 0.15s, box-shadow 0.15s;
}

.search-box input:focus {
    border-color: var(--border-strong);
    box-shadow: 0 0 0 4px rgba(31, 77, 184, 0.08);
}

/* Category filters */
.category-filters {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 16px;
}

.category-filter-btn {
    padding: 8px 12px;
    border: 1px solid var(--border);
    border-radius: 7px;
    background: rgba(255, 255, 255, 0.55);
    color: var(--muted);
    font-weight: 600;
    font-size: 13px;
    cursor: pointer;
    transition: color 0.15s, background 0.15s, border-color 0.15s;
}

.category-filter-btn:hover {
    color: var(--muted-strong);
    background: rgba(255, 255, 255, 0.92);
    border-color: var(--border-strong);
}

.category-filter-btn.active {
    background: var(--text);
    color: #fff;
    border-color: var(--text);
}

/* Stats */
.stats-bar {
    display: flex;
    flex-wrap: wrap;
    gap: 10px 14px;
    margin-bottom: 4px;
    padding-top: 4px;
}

.stat-item {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    color: var(--muted);
    font-size: 14px;
}

.stat-item strong {
    color: var(--muted-strong);
    font-weight: 700;
    text-transform: capitalize;
}

/* Sections */
.section {
    margin: 42px 0 28px;
}

.section-title {
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: var(--muted);
    margin: 0 0 10px;
    font-weight: 700;
}

.section-intro {
    margin: 0 0 18px;
    color: var(--muted);
    font-size: 17px;
    max-width: 700px;
}

.briefing-shell {
    display: grid;
    grid-template-columns: minmax(0, 1.12fr) minmax(320px, 0.88fr);
    gap: 28px;
    align-items: start;
}

.briefing-lead {
    background: var(--card);
    border: 1px solid rgba(0, 0, 0, 0.04);
    border-radius: 12px;
    padding: 26px 28px 24px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.03);
}

.briefing-kicker,
.category-label {
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--primary);
}

.briefing-kicker {
    color: var(--muted-strong);
}

.eyebrow-row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 10px 14px;
}

.briefing-lead h3 {
    font-size: 42px;
    line-height: 1.08;
    letter-spacing: -0.03em;
    margin: 14px 0 16px;
    max-width: 13ch;
}

.briefing-lead p {
    font-size: 21px;
    line-height: 1.5;
    color: var(--muted-strong);
    margin: 0 0 18px;
    max-width: 28ch;
}

.briefing-side {
    border-top: 2px solid var(--text);
    padding-top: 10px;
}

.briefing-side-title {
    margin: 0 0 14px;
    font-size: 18px;
    letter-spacing: -0.01em;
}

.briefing-list {
    list-style: none;
    padding: 0;
    margin: 0;
}

.briefing-item {
    border-top: 1px solid var(--border);
    padding: 16px 0;
}

.briefing-item:first-child {
    border-top: 0;
    padding-top: 0;
}

.briefing-item article {
    display: grid;
    grid-template-columns: 32px minmax(0, 1fr);
    gap: 14px;
}

.briefing-rank {
    color: var(--muted);
    font-size: 14px;
    font-weight: 700;
    padding-top: 2px;
}

.briefing-copy h3 {
    margin: 6px 0 8px;
    font-size: 25px;
    line-height: 1.18;
    letter-spacing: -0.02em;
}

.briefing-copy p {
    margin: 0 0 10px;
    color: var(--muted);
    line-height: 1.5;
}

/* Category sections */
.category-section {
    margin-bottom: 38px;
}

.category-heading {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 12px;
    padding-bottom: 12px;
    margin-bottom: 4px;
    border-bottom: 1px solid var(--border-strong);
}

.category-title {
    font-size: 24px;
    font-weight: 760;
    margin: 0;
    letter-spacing: -0.02em;
}

.category-count {
    margin: 0;
    font-size: 14px;
    color: var(--muted);
}

.news-list {
    display: block;
}

/* News cards */
.news-card {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 18px;
    padding: 18px 0;
    margin: 0;
    border-bottom: 1px solid var(--border);
}

.news-card-compact h3 {
    font-size: 24px;
}

.news-card h3 {
    font-size: 31px;
    line-height: 1.16;
    margin: 10px 0 10px;
    letter-spacing: -0.025em;
    max-width: 24ch;
}

.news-card p {
    color: var(--muted-strong);
    margin: 0;
    line-height: 1.58;
    max-width: var(--reading-width);
}

.card-footer {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    justify-content: space-between;
    gap: 12px;
    min-width: 156px;
}

.source {
    color: var(--muted);
    font-size: 14px;
    line-height: 1.45;
}

.source-inline {
    display: inline;
}

.source-block {
    display: none;
}

.read-link {
    color: var(--primary);
    font-weight: 600;
    white-space: nowrap;
    align-self: flex-end;
}

.read-link:hover {
    color: var(--primary-hover);
}

/* Search */
.results-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin: 10px 0 2px;
}

.results-meta {
    margin: 0;
    color: var(--muted);
    font-size: 14px;
}

/* Archive */
.archive-group {
    margin: 28px 0 34px;
}

.archive-group-title {
    margin: 0 0 10px;
    font-size: 18px;
    color: var(--muted-strong);
    letter-spacing: -0.01em;
}

.archive-list {
    list-style: none;
    margin: 0;
    padding: 0;
    border-top: 1px solid var(--border);
}

.archive-entry {
    border-bottom: 1px solid var(--border);
}

.archive-entry a {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 14px 0;
}

.archive-entry a:hover .archive-date,
.archive-entry a:hover .archive-arrow {
    color: var(--primary);
}

.archive-date {
    font-size: 18px;
    font-weight: 600;
    color: var(--text);
}

.archive-arrow {
    color: var(--muted);
    font-size: 22px;
}

/* Empty state */
.empty-state {
    color: var(--muted);
    padding: 40px 0;
    text-align: center;
    font-size: 16px;
}

/* Footer */
.site-footer {
    border-top: 1px solid var(--border);
    background: transparent;
    margin-top: 68px;
    padding: 28px 0;
    color: var(--muted);
    font-size: 14px;
}

.footer-inner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
}

.footer-links {
    display: flex;
    gap: 16px;
}

.footer-links a {
    color: var(--muted);
}

.footer-links a:hover {
    color: var(--primary);
}

/* Responsive */
@media (max-width: 1024px) {
    .briefing-shell {
        grid-template-columns: 1fr;
        gap: 20px;
    }

    .briefing-lead h3 {
        max-width: 100%;
    }

    .news-card {
        grid-template-columns: 1fr;
    }

    .card-footer {
        align-items: flex-start;
        min-width: 0;
        padding-top: 2px;
    }

    .source-inline {
        display: none;
    }

    .source-block {
        display: inline;
    }

    .read-link {
        align-self: flex-start;
    }
}

@media (max-width: 900px) {
    .hero h1 {
        font-size: 42px;
    }

    .hero-lead {
        font-size: 18px;
    }

    .briefing-lead h3 {
        font-size: 34px;
    }

    .briefing-lead p {
        font-size: 19px;
        max-width: 100%;
    }

    .briefing-copy h3,
    .news-card h3,
    .news-card-compact h3 {
        font-size: 24px;
    }
}

@media (max-width: 700px) {
    .site-wrapper,
    .header-inner,
    .footer-inner {
        padding: 0 16px;
    }

    .menu-toggle {
        display: flex;
        margin-left: auto;
    }

    .nav-links {
        display: none;
        position: absolute;
        top: 100%;
        left: 0;
        right: 0;
        background: rgba(248, 246, 241, 0.98);
        backdrop-filter: blur(10px);
        border-bottom: 1px solid var(--border);
        flex-direction: column;
        align-items: flex-start;
        padding: 12px 16px 18px;
        gap: 4px;
    }

    .nav-links.open {
        display: flex;
    }

    .nav-links a {
        width: 100%;
        padding: 10px 12px;
    }

    .header-date {
        display: none;
    }

    .hero {
        padding: 26px 0 10px;
    }

    .hero h1 {
        font-size: 32px;
        max-width: 100%;
    }

    .hero-lead {
        font-size: 16px;
        margin-bottom: 18px;
    }

    .search-box input {
        padding-top: 15px;
        padding-bottom: 15px;
    }

    .stats-bar {
        gap: 8px 12px;
    }

    .section {
        margin: 28px 0 22px;
    }

    .section-intro {
        font-size: 15px;
        margin-bottom: 14px;
    }

    .briefing-lead {
        padding: 18px 18px 16px;
    }

    .briefing-lead h3 {
        font-size: 27px;
        margin-top: 10px;
        margin-bottom: 12px;
    }

    .briefing-lead p {
        font-size: 17px;
    }

    .briefing-copy h3,
    .news-card h3,
    .news-card-compact h3 {
        font-size: 21px;
    }

    .briefing-item article {
        grid-template-columns: 24px minmax(0, 1fr);
        gap: 12px;
    }

    .category-heading {
        align-items: flex-end;
    }

    .category-title {
        font-size: 20px;
    }

    .news-card {
        padding: 14px 0;
        gap: 10px;
    }

    .footer-inner {
        flex-direction: column;
        align-items: flex-start;
        gap: 8px;
    }

    .archive-date {
        font-size: 17px;
    }
}

@media (max-width: 480px) {
    .category-filters {
        margin-bottom: 12px;
    }

    .category-filter-btn {
        padding: 8px 11px;
        font-size: 12px;
    }

    .hero-date,
    .source,
    .results-meta,
    .category-count,
    .stat-item {
        font-size: 13px;
    }
}
"""


def get_js():
    """Return the shared site JavaScript."""
    return """document.addEventListener("DOMContentLoaded", function () {
    // Mobile menu
    const menuToggle = document.querySelector(".menu-toggle");
    const navLinks = document.querySelector(".nav-links");

    if (menuToggle && navLinks) {
        menuToggle.addEventListener("click", function () {
            const isOpen = navLinks.classList.toggle("open");
            menuToggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
        });
    }

    // Home page search + category filtering
    const homeSearchInput = document.querySelector("#home-search-input");
    const newsCards = document.querySelectorAll(".news-card");
    const categoryButtons = document.querySelectorAll(".category-filter-btn");
    const categorySections = document.querySelectorAll(".category-section");
    let selectedCategory = "all";

    function filterHome() {
        const query = (homeSearchInput && homeSearchInput.value || "").toLowerCase();

        newsCards.forEach(function (card) {
            const text = card.dataset.search || "";
            const category = card.dataset.category || "genel";

            const matchesSearch = text.includes(query);
            const matchesCategory = selectedCategory === "all" || category === selectedCategory;

            card.style.display = matchesSearch && matchesCategory ? "" : "none";
        });

        categorySections.forEach(function (section) {
            const visibleCards = Array.from(section.querySelectorAll(".news-card")).filter(function (card) {
                return card.style.display !== "none";
            });
            section.style.display = visibleCards.length ? "" : "none";
        });
    }

    if (homeSearchInput) {
        homeSearchInput.addEventListener("input", filterHome);
    }

    if (categoryButtons && categoryButtons.length) {
        categoryButtons.forEach(function (button) {
            button.addEventListener("click", function () {
                categoryButtons.forEach(function (btn) {
                    btn.classList.remove("active");
                });

                button.classList.add("active");
                selectedCategory = button.dataset.category;

                filterHome();
            });
        });
    }

    // Search page
    const searchInput = document.querySelector("#search-input");
    const resultsContainer = document.querySelector("#search-results");
    const searchDataEl = document.querySelector("#search-data");
    const resultsMeta = document.querySelector("#search-results-meta");

    if (searchInput && resultsContainer && searchDataEl) {
        let newsData = [];
        try {
            newsData = JSON.parse(searchDataEl.textContent) || [];
        } catch (e) {
            newsData = [];
        }

        function escapeHtml(str) {
            return String(str)
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        }

        function formatPublished(item) {
            const raw = item.published_at || item.published || "";
            if (!raw) return "";
            const d = new Date(raw);
            if (isNaN(d.getTime())) return escapeHtml(raw);
            const months = [
                "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
                "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"
            ];
            return d.getDate() + " " + months[d.getMonth()] + " " + d.getFullYear() +
                ", " + String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
        }

        function buildCard(item) {
            const card = document.createElement("article");
            card.className = "news-card";

            const category = item.category ? '<span class="category-label">' + escapeHtml(item.category.toUpperCase()) + "</span>" : "";
            const meta = [item.source, formatPublished(item)].filter(Boolean).join(" · ");
            const title = escapeHtml(item.title || "");
            const summary = escapeHtml(item.summary || "");
            const link = escapeHtml(item.link || "#");

            card.innerHTML =
                '<div class="news-card-body">' +
                '<div class="eyebrow-row">' + category + '<span class="source source-inline">' + escapeHtml(meta) + '</span></div>' +
                "<h3>" + title + "</h3>" +
                "<p>" + summary + "</p>" +
                '</div>' +
                '<div class="card-footer"><span class="source source-block">' + escapeHtml(meta) + '</span>' +
                '<a class="read-link" href="' + link + '" target="_blank" rel="noopener noreferrer">Haberi oku</a></div>';

            return card;
        }

        function showResults(items) {
            resultsContainer.innerHTML = "";
            if (resultsMeta) {
                const count = items ? items.length : 0;
                resultsMeta.textContent = count + " sonuç";
            }

            if (!items || !items.length) {
                resultsContainer.innerHTML = '<p class="empty-state">Sonuç bulunamadı.</p>';
                return;
            }

            const fragment = document.createDocumentFragment();
            items.forEach(function (item) {
                fragment.appendChild(buildCard(item));
            });
            resultsContainer.appendChild(fragment);
        }

        function filterSearch() {
            const query = (searchInput.value || "").toLowerCase();

            const filtered = newsData.filter(function (item) {
                const text = [
                    item.title || "",
                    item.summary || "",
                    item.category || "",
                    item.source || "",
                    item.published || ""
                ].join(" ").toLowerCase();

                return text.includes(query);
            });

            showResults(filtered);
        }

        showResults(newsData);
        searchInput.addEventListener("input", filterSearch);
    }
});
"""
