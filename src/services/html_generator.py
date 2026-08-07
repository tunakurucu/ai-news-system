import html
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

_TURKISH_MONTHS = [
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"
]


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


def _meta_line(item):
    """Build 'Source · date' metadata with a safe fallback."""
    source = _escape(item.get("source", ""))
    date = _format_published(item)
    if date:
        return f"{source} · {date}"
    return source


def generate_news_html(news_items, stats):
    html = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>Günün Haberleri</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 1000px;
            margin: 40px auto;
            line-height: 1.6;
        }

        .stats-grid {
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            margin-bottom: 30px;
        }

        .stat-card {
            border: 1px solid #ddd;
            padding: 12px 20px;
            border-radius: 8px;
            min-width: 140px;
            background: #f7f7f7;
        }

        .stat-card strong {
            display: block;
            color: #444;
        }

        .stat-card span {
            font-size: 28px;
            font-weight: bold;
        }

        .featured-list {
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 16px 24px;
            background: #fafafa;
            margin-bottom: 35px;
        }

        .featured-list li {
            margin-bottom: 8px;
        }

        .category-title {
            margin-top: 40px;
            border-bottom: 2px solid #222;
            padding-bottom: 6px;
        }

        .news-card {
            border: 1px solid #ddd;
            padding: 16px;
            margin-bottom: 16px;
            border-radius: 8px;
        }

        .news-card h3 {
            margin-top: 0;
        }

        .source {
            font-size: 13px;
            color: #777;
            margin-bottom: 8px;
        }

        a {
            color: #0066cc;
        }

        .search-box {
            margin: 25px 0;
        }

        .search-box input {
            width: 100%;
            padding: 12px 14px;
            font-size: 16px;
            border: 1px solid #ddd;
            border-radius: 8px;
        }

        .category-filters {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin: 20px 0 30px;
        }

        .category-filter-btn {
            padding: 8px 14px;
            border: 1px solid #ddd;
            border-radius: 999px;
            background: #f7f7f7;
            cursor: pointer;
        }

        .category-filter-btn.active {
            background: #222;
            color: white;
        }
    </style>
</head>
<body>

<nav>
    <a href="index.html">Güncel Haberler</a> |
    <a href="archive.html">Arşiv</a> |
    <a href="search.html">Arama</a>
</nav>

<h1>Günün Haberleri</h1>

<div class="search-box">
    <input type="text" id="home-search-input" placeholder="Güncel haberlerde ara...">
</div>

<div class="category-filters">
    <button class="category-filter-btn active" data-category="all">Tümü</button>
    <button class="category-filter-btn" data-category="ekonomi">Ekonomi</button>
    <button class="category-filter-btn" data-category="teknoloji">Teknoloji</button>
    <button class="category-filter-btn" data-category="dünya">Dünya</button>
    <button class="category-filter-btn" data-category="gümrük">Gümrük</button>
    <button class="category-filter-btn" data-category="genel">Genel</button>
</div>

"""

    html += """
    <div class="stats-grid">
"""

    for key, value in stats.items():
        html += f"""
        <div class="stat-card">
            <strong>{_escape(key)}</strong>
            <span>{_escape(value)}</span>
        </div>
"""

    html += """
    </div>
"""

    top_news = sorted(
        news_items,
        key=lambda x: x.get("importance_score", 0),
        reverse=True
    )[:5]

    html += """
    <h2>🔥 Öne Çıkan Haberler</h2>
    <ul class="featured-list">
"""

    for item in top_news:
        link = (item.get("link") or "").strip() or "#"
        html += f"""
        <li>
            <a href="{_escape(link)}" target="_blank" rel="noopener noreferrer">
                <strong>{_escape(item.get("title", ""))}</strong>
            </a>
        </li>
"""

    html += """
    </ul>
"""

    grouped_news = {}

    for item in news_items:
        category = item.get("category", "genel")
        if category not in grouped_news:
            grouped_news[category] = []
        grouped_news[category].append(item)

    for category, items in grouped_news.items():
        html += f"""
    <h2 class="category-title">{_escape(category.upper())}</h2>
"""

        for item in items:
            search_text = " ".join([
                str(item.get("title", "")),
                str(item.get("summary", "")),
                str(item.get("category", "")),
                str(item.get("source", "")),
            ]).lower()
            search_text = re.sub(r"\s+", " ", search_text).strip()

            link = (item.get("link") or "").strip() or "#"

            html += f"""
                <div
                    class="news-card"
                    data-search="{_escape(search_text)}"
                    data-category="{_escape(item.get('category', 'genel'))}"
                >
                    <h3>{_escape(item.get("title", ""))}</h3>
                    <p>{_escape(item.get("summary", ""))}</p>
                    <div class="source">{_meta_line(item)}</div>
                    <a href="{_escape(link)}" target="_blank" rel="noopener noreferrer">Haberi Oku</a>
                </div>
            """

    html += """
        <script>
            const homeSearchInput = document.querySelector("#home-search-input");
            const newsCards = document.querySelectorAll(".news-card");
            const categoryButtons = document.querySelectorAll(".category-filter-btn");

            let selectedCategory = "all";

            function filterNews() {
                const query = homeSearchInput.value.toLowerCase();

                newsCards.forEach(function (card) {
                    const text = card.dataset.search || "";
                    const category = card.dataset.category || "genel";

                    const matchesSearch = text.includes(query);
                    const matchesCategory =
                        selectedCategory === "all" || category === selectedCategory;

                    if (matchesSearch && matchesCategory) {
                        card.style.display = "block";
                    } else {
                        card.style.display = "none";
                    }
                });
            }

            homeSearchInput.addEventListener("input", filterNews);

            categoryButtons.forEach(function (button) {
                button.addEventListener("click", function () {
                    categoryButtons.forEach(function (btn) {
                        btn.classList.remove("active");
                    });

                    button.classList.add("active");
                    selectedCategory = button.dataset.category;

                    filterNews();
                });
            });
        </script>

    </body>
    </html>
    """

    return html
