from pathlib import Path
from datetime import datetime
import json

from services.news_fetcher import fetch_news
from services.news_cleaner import clean_news
from services.news_filter import filter_news
from services.news_categorizer import add_categories
from services.statistics import generate_statistics
from services.script_generator import generate_news_script
from services.html_generator import generate_news_html, generate_search_html, get_css, get_js
from services.story_clustering import generate_stories
from services.archive_generator import generate_archive, generate_search_index
from services.publisher import publish
from services.newsletter_sender import send_newsletter

from utils.file_helper import save_json, save_text
from utils.logger import get_logger
import os


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_json(path: Path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _generate_historical_daily_pages(output_dir: Path) -> None:
    raw_dir = PROJECT_ROOT / "data" / "raw"
    stats_dir = PROJECT_ROOT / "data" / "stats"

    for raw_file in sorted(raw_dir.glob("*-news.json")):
        if raw_file.name == "latest-news.json":
            continue

        date_name = raw_file.stem.replace("-news", "")
        items = _load_json(raw_file)

        stats_file = stats_dir / f"{date_name}-statistics.json"
        if stats_file.exists():
            stats = _load_json(stats_file)
        else:
            stats = generate_statistics(items)

        html = generate_news_html(
            items,
            stats,
            page_heading="Günün Haberleri",
            hero_date=date_name,
            hero_lead="Bu güne ait derlenmiş haber akışı. Kaynak ve yayın saatleri korunur.",
        )
        save_text(html, output_dir / f"{date_name}-news.html")


def main():
    logger = get_logger()
    today = datetime.now().strftime("%Y-%m-%d")

    logger.info("Uygulama başlatıldı")
    print("AI Haber Yayın Sistemi başlatıldı...")

    news_items = fetch_news()
    cleaned_news = clean_news(news_items)
    filtered_news = filter_news(cleaned_news)
    categorized_news = add_categories(filtered_news)

    stats = generate_statistics(categorized_news)
    stories = generate_stories(categorized_news)
    script = generate_news_script(categorized_news)
    html = generate_news_html(categorized_news, stats)
    css = get_css()
    js = get_js()

    latest_json_file = PROJECT_ROOT / "data" / "raw" / "latest-news.json"
    archive_json_file = PROJECT_ROOT / "data" / "raw" / f"{today}-news.json"

    latest_stats_file = PROJECT_ROOT / "data" / "stats" / "latest-statistics.json"
    archive_stats_file = PROJECT_ROOT / "data" / "stats" / f"{today}-statistics.json"

    latest_stories_file = PROJECT_ROOT / "data" / "stories" / "latest-stories.json"
    archive_stories_file = PROJECT_ROOT / "data" / "stories" / f"{today}-stories.json"

    latest_script_file = PROJECT_ROOT / "outputs" / "scripts" / "daily-news-script.txt"
    archive_script_file = PROJECT_ROOT / "outputs" / "scripts" / f"{today}-script.txt"

    latest_html_file = PROJECT_ROOT / "outputs" / "html" / "index.html"
    archive_html_file = PROJECT_ROOT / "outputs" / "html" / f"{today}-news.html"
    archive_page_file = PROJECT_ROOT / "outputs" / "html" / "archive.html"
    search_page_file = PROJECT_ROOT / "outputs" / "html" / "search.html"

    css_file = PROJECT_ROOT / "outputs" / "html" / "assets" / "css" / "news.css"
    js_file = PROJECT_ROOT / "outputs" / "html" / "assets" / "js" / "news.js"

    save_json(categorized_news, latest_json_file)
    save_json(categorized_news, archive_json_file)

    save_json(stats, latest_stats_file)
    save_json(stats, archive_stats_file)

    save_json(stories, latest_stories_file)
    save_json(stories, archive_stories_file)

    save_text(script, latest_script_file)
    save_text(script, archive_script_file)

    public_stats_file = (
        PROJECT_ROOT
        / "outputs"
        / "html"
        / "data"
        / "stats"
        / "latest-statistics.json"
    )
    public_stats_file.parent.mkdir(parents=True, exist_ok=True)

    search_index_file = (
        PROJECT_ROOT
        / "data"
        / "index"
        / "search-index.json"
    )
    public_search_index_file = (
        PROJECT_ROOT
        / "outputs"
        / "html"
        / "data"
        / "index"
        / "search-index.json"
    )

    search_index = generate_search_index(PROJECT_ROOT)
    search_html = generate_search_html(search_index)
    archive_html = generate_archive(PROJECT_ROOT)

    save_json(stats, public_stats_file)
    save_text(html, latest_html_file)
    save_text(html, archive_html_file)
    save_text(search_html, search_page_file)
    save_text(archive_html, archive_page_file)
    save_text(css, css_file)
    save_text(js, js_file)
    _generate_historical_daily_pages(PROJECT_ROOT / "outputs" / "html")

    save_json(search_index, public_search_index_file)
    save_json(search_index, search_index_file)

    publish(PROJECT_ROOT)

    send_newsletter_enabled = os.getenv("SEND_NEWSLETTER")
    print("SEND_NEWSLETTER değeri:", repr(send_newsletter_enabled))

    if send_newsletter_enabled == "true":
        print("Newsletter gönderme aşamasına girildi.")

        email_result = send_newsletter(categorized_news, stats)

        print("Bülten gönderildi:", email_result)
    else:
        print("Newsletter gönderimi kapalı.")

    print("\n--- HABER İSTATİSTİKLERİ ---")
    for key, value in stats.items():
        print(f"{key}: {value}")

    logger.info(f"{len(news_items)} adet ham haber çekildi")
    logger.info(f"{len(filtered_news)} adet filtrelenmiş haber kaydedildi")
    logger.info(f"HTML oluşturuldu: {latest_html_file}")
    logger.info(f"Yayın klasörü güncellendi: {PROJECT_ROOT / 'docs'}")

    print("Haberler çekildi.")
    print(f"Ham haber sayısı: {len(news_items)}")
    print(f"Filtrelenmiş haber sayısı: {len(filtered_news)}")
    print(f"Güncel HTML: {latest_html_file}")
    print(f"Arşiv HTML: {archive_html_file}")
    print(f"Arşiv Sayfası: {archive_page_file}")
    print(f"Arama Sayfası: {search_page_file}")
    print(f"Search Index: {search_index_file}")
    print("Yayın klasörü güncellendi:", PROJECT_ROOT / "docs")


if __name__ == "__main__":
    main()
