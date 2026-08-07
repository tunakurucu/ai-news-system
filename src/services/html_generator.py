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


def _card(item):
    """Render a single news card."""
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

    return f"""<article class="news-card" data-search="{_escape(search_text)}" data-category="{_escape(item.get('category', 'genel'))}">
    <span class="category-badge">{category}</span>
    <h3>{title}</h3>
    <p>{summary}</p>
    <div class="card-footer">
        <span class="source">{meta}</span>
        <a class="read-link" href="{_escape(link)}" target="_blank" rel="noopener noreferrer">Haberi oku →</a>
    </div>
</article>
"""


def _featured_card(item, large=False):
    """Render a featured/top-story card."""
    category = _escape(item.get("category", "genel").upper())
    title = _escape(item.get("title", ""))
    summary = _escape(item.get("summary", ""))
    meta = _meta_line(item)
    link = (item.get("link") or "").strip() or "#"

    return f"""<article class="featured-card">
    <span class="category-badge">{category}</span>
    <h3>{title}</h3>
    {'<p>' + summary + '</p>' if summary else ''}
    <div class="card-footer">
        <span class="source">{meta}</span>
        <a class="read-link" href="{_escape(link)}" target="_blank" rel="noopener noreferrer">Haberi oku →</a>
    </div>
</article>
"""


def _stats_html(stats):
    """Render a compact stats bar."""
    if not stats:
        return ""
    pills = []
    for key, value in stats.items():
        if key == "generated_at":
            continue
        pills.append(
            f'<span class="stat-pill"><strong>{_escape(key)}</strong> {_escape(value)}</span>'
        )
    if not pills:
        return ""
    return f'<div class="stats-bar">{"".join(pills)}</div>\n'


def _featured_html(top_news):
    """Render the top-stories section."""
    if not top_news:
        return '<p class="empty-state">Bugün için öne çıkan haber bulunamadı.</p>'

    main = _featured_card(top_news[0], large=True)
    side = "".join([_featured_card(item) for item in top_news[1:5]])

    return f"""<div class="featured-grid">
    <div class="featured-main">{main}</div>
    <div class="featured-side">{side}</div>
</div>
"""


def _category_sections_html(grouped_news):
    """Render grouped news cards by category."""
    sections = []
    for category, items in grouped_news.items():
        cards = "".join([_card(item) for item in items])
        sections.append(
            f"""<section class="category-section">
    <h2 class="category-title">{_escape(category.upper())}</h2>
    {cards}
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
    <span class="search-icon" aria-hidden="true">🔍</span>
    <input type="text" id="{input_id}" placeholder="{_escape(placeholder)}" autocomplete="off">
</div>
"""


def generate_news_html(news_items, stats):
    """Generate the redesigned homepage."""
    top_news = sorted(
        news_items,
        key=lambda x: x.get("importance_score", 0),
        reverse=True
    )[:5]

    grouped_news = {}
    for item in news_items:
        category = item.get("category", "genel")
        grouped_news.setdefault(category, []).append(item)

    body = f"""<main class="site-wrapper">
    <section class="hero">
        <div class="hero-text">
            <h1>Bugünün Haberleri</h1>
            <p class="hero-date">{_format_today()}</p>
            <p class="hero-lead">RSS kaynaklarından derlenen güncel haber özetleri. Kaynakları ve yayınlanma zamanlarını görebilirsiniz.</p>
        </div>
        {_search_box('home-search-input', 'Güncel haberlerde ara...')}
        <div class="category-filters">
            {_category_filter_buttons()}
        </div>
        {_stats_html(stats)}
    </section>

    <section class="section">
        <h2 class="section-title">Bugünün Özeti</h2>
        {_featured_html(top_news)}
    </section>

    {_category_sections_html(grouped_news)}
</main>
"""

    return _page("Günün Haberleri", body, active="index")


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
        <p class="hero-lead">Arşivdeki ve bugünün haberlerinde başlık, özet, kategori veya kaynak ara.</p>
        {_search_box('search-input', 'Başlık, konu, kategori veya kaynak ara...')}
    </section>

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

    cards = []
    for file in archive_files:
        date_name = file.stem.replace("-news", "")
        try:
            dt = datetime.strptime(date_name, "%Y-%m-%d")
            display = _format_date_tr(dt)
        except Exception:
            display = _escape(date_name)

        href = f"{date_name}-news.html"
        cards.append(
            f'<a class="archive-card" href="{_escape(href)}">'
            f'<span class="archive-date">{_escape(display)}</span>'
            f'</a>'
        )

    if not cards:
        grid = '<p class="empty-state">Henüz arşivlenmiş haber bulunmuyor.</p>'
    else:
        grid = f'<div class="archive-grid">{"".join(cards)}</div>'

    body = f"""<main class="site-wrapper">
    <section class="hero hero-small">
        <h1>Haber Arşivi</h1>
        <p class="hero-lead">Geçmiş günlere ait haber özetlerine göz atın.</p>
    </section>
    {grid}
</main>
"""

    return _page("Haber Arşivi", body, active="archive")


def get_css():
    """Return the shared site stylesheet."""
    return """:root {
    --bg: #F5F7FA;
    --card: #FFFFFF;
    --primary: #2563EB;
    --primary-hover: #1D4ED8;
    --border: #E5E7EB;
    --text: #111827;
    --muted: #6B7280;
    --max-width: 1200px;
    --radius: 16px;
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
    font-family: "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, "Helvetica Neue", Arial, sans-serif;
    -webkit-font-smoothing: antialiased;
    line-height: 1.55;
    min-height: 100vh;
}

a {
    color: var(--primary);
    text-decoration: none;
}

a:hover {
    color: var(--primary-hover);
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
    background: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur(10px);
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
    font-size: 22px;
    font-weight: 800;
    letter-spacing: -0.02em;
    color: var(--text);
    margin-right: auto;
}

.brand:hover {
    color: var(--primary);
}

.nav-links {
    display: flex;
    align-items: center;
    gap: 6px;
}

.nav-links a {
    color: var(--muted);
    font-weight: 500;
    padding: 8px 14px;
    border-radius: 8px;
    transition: color 0.15s, background 0.15s;
}

.nav-links a:hover,
.nav-links a.active {
    color: var(--primary);
    background: rgba(37, 99, 235, 0.06);
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
    padding: 56px 0 24px;
}

.hero-small {
    padding: 40px 0 16px;
}

.hero h1 {
    font-size: 42px;
    font-weight: 800;
    letter-spacing: -0.03em;
    margin: 0 0 8px;
    line-height: 1.1;
}

.hero-date {
    color: var(--muted);
    font-size: 16px;
    margin: 0 0 12px;
    font-weight: 500;
}

.hero-lead {
    color: var(--muted);
    font-size: 18px;
    max-width: 640px;
    margin: 0 0 28px;
    line-height: 1.5;
}

/* Search */
.search-box {
    position: relative;
    max-width: 720px;
    margin: 0 0 20px;
}

.search-icon {
    position: absolute;
    left: 18px;
    top: 50%;
    transform: translateY(-50%);
    font-size: 18px;
    opacity: 0.5;
    pointer-events: none;
}

.search-box input {
    width: 100%;
    padding: 16px 20px 16px 50px;
    border: 1px solid var(--border);
    border-radius: 999px;
    background: var(--card);
    font-size: 16px;
    color: var(--text);
    outline: none;
    transition: border-color 0.15s, box-shadow 0.15s;
}

.search-box input:focus {
    border-color: var(--primary);
    box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.08);
}

/* Category filters */
.category-filters {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-bottom: 24px;
}

.category-filter-btn {
    padding: 8px 16px;
    border: 1px solid var(--border);
    border-radius: 999px;
    background: transparent;
    color: var(--muted);
    font-weight: 600;
    font-size: 14px;
    cursor: pointer;
    transition: color 0.15s, background 0.15s, border-color 0.15s;
}

.category-filter-btn:hover {
    color: var(--primary);
    background: rgba(37, 99, 235, 0.06);
    border-color: rgba(37, 99, 235, 0.2);
}

.category-filter-btn.active {
    background: var(--primary);
    color: #fff;
    border-color: var(--primary);
}

/* Stats */
.stats-bar {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-bottom: 8px;
}

.stat-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 14px;
    border: 1px solid var(--border);
    border-radius: 999px;
    background: var(--card);
    color: var(--muted);
    font-size: 13px;
}

.stat-pill strong {
    color: var(--text);
    font-weight: 700;
}

/* Sections */
.section {
    margin: 56px 0 40px;
}

.section-title {
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--muted);
    margin: 0 0 18px;
    font-weight: 700;
}

/* Featured */
.featured-grid {
    display: grid;
    grid-template-columns: 1.2fr 0.8fr;
    gap: 20px;
}

.featured-main,
.featured-side {
    display: flex;
    flex-direction: column;
    gap: 20px;
}

.featured-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 24px;
    box-shadow: 0 4px 12px rgba(16, 24, 40, 0.03);
    transition: transform 0.12s, box-shadow 0.12s;
    display: flex;
    flex-direction: column;
    flex: 1;
}

.featured-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 14px 32px rgba(16, 24, 40, 0.08);
}

.featured-main {
    justify-content: center;
}

.featured-main h3 {
    font-size: 28px;
}

.featured-card h3 {
    font-size: 20px;
    line-height: 1.25;
    margin: 0 0 10px;
    letter-spacing: -0.01em;
}

.featured-card p {
    color: var(--muted);
    margin: 0 0 16px;
    line-height: 1.55;
}

/* Category sections */
.category-section {
    margin-bottom: 48px;
}

.category-title {
    font-size: 28px;
    font-weight: 800;
    margin: 0 0 20px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--border);
    letter-spacing: -0.01em;
}

/* News cards */
.news-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 24px;
    margin-bottom: 16px;
    box-shadow: 0 4px 12px rgba(16, 24, 40, 0.03);
    transition: transform 0.12s, box-shadow 0.12s;
}

.news-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 14px 32px rgba(16, 24, 40, 0.08);
}

.category-badge {
    display: inline-block;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 700;
    color: var(--primary);
    background: rgba(37, 99, 235, 0.06);
    padding: 4px 8px;
    border-radius: 6px;
    margin-bottom: 12px;
}

.news-card h3 {
    font-size: 22px;
    line-height: 1.25;
    margin: 0 0 10px;
    letter-spacing: -0.01em;
}

.news-card p {
    color: var(--muted);
    margin: 0 0 16px;
    line-height: 1.6;
}

.card-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    flex-wrap: wrap;
}

.source {
    color: var(--muted);
    font-size: 14px;
}

.read-link {
    color: var(--primary);
    font-weight: 600;
    white-space: nowrap;
}

.read-link:hover {
    color: var(--primary-hover);
}

/* Archive */
.archive-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 16px;
    margin: 24px 0 48px;
}

.archive-card {
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 22px 18px;
    text-align: center;
    font-weight: 600;
    color: var(--text);
    box-shadow: 0 4px 12px rgba(16, 24, 40, 0.03);
    transition: transform 0.12s, box-shadow 0.12s, border-color 0.12s;
}

.archive-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 12px 28px rgba(16, 24, 40, 0.08);
    border-color: var(--primary);
    color: var(--primary);
}

.archive-date {
    font-size: 15px;
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
    background: var(--card);
    margin-top: 80px;
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
@media (max-width: 900px) {
    .featured-grid {
        grid-template-columns: 1fr;
    }

    .hero h1 {
        font-size: 34px;
    }

    .featured-main h3 {
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
        background: rgba(255, 255, 255, 0.98);
        backdrop-filter: blur(10px);
        border-bottom: 1px solid var(--border);
        flex-direction: column;
        align-items: flex-start;
        padding: 12px 16px 20px;
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
        padding: 36px 0 16px;
    }

    .hero h1 {
        font-size: 28px;
    }

    .hero-lead {
        font-size: 16px;
    }

    .news-card {
        padding: 18px;
    }

    .news-card h3 {
        font-size: 18px;
    }

    .card-footer {
        flex-direction: column;
        align-items: flex-start;
        gap: 10px;
    }

    .footer-inner {
        flex-direction: column;
        align-items: flex-start;
        gap: 8px;
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

            const category = item.category ? '<span class="category-badge">' + escapeHtml(item.category.toUpperCase()) + "</span>" : "";
            const meta = [item.source, formatPublished(item)].filter(Boolean).join(" · ");
            const title = escapeHtml(item.title || "");
            const summary = escapeHtml(item.summary || "");
            const link = escapeHtml(item.link || "#");

            card.innerHTML = category +
                "<h3>" + title + "</h3>" +
                "<p>" + summary + "</p>" +
                '<div class="card-footer"><span class="source">' + escapeHtml(meta) + '</span>' +
                '<a class="read-link" href="' + link + '" target="_blank" rel="noopener noreferrer">Haberi oku →</a></div>';

            return card;
        }

        function showResults(items) {
            resultsContainer.innerHTML = "";

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
