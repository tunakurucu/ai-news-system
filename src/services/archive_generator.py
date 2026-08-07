from pathlib import Path
import json

from services import html_generator


def generate_archive(project_root):
    """Generate a modern archive page listing past daily news files."""
    return html_generator.generate_archive_html(project_root)


def generate_search_index(project_root):
    raw_folder = Path(project_root) / "data" / "raw"

    all_news = []
    seen_links = set()

    for file in raw_folder.glob("*-news.json"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                news = json.load(f)

                if isinstance(news, list):
                    for item in news:
                        link = str(item.get("link", "")).strip()

                        if not link:
                            continue

                        if link in seen_links:
                            continue

                        seen_links.add(link)

                        all_news.append(item)
        except Exception as e:
            print(f"Hata: {file.name} -> {e}")

    return all_news
