import os
import sys
import unittest
import html

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from services import html_generator as hg


def _base_item(**overrides):
    return {
        "title": "OpenAI announces new model with enough characters",
        "summary": "This summary is long enough to pass any length filter and be displayed.",
        "source": "Reuters",
        "link": "http://example.com/openai",
        "category": "teknoloji",
        "published_at": "2026-08-07T14:32:00+00:00",
        "importance_score": 5,
        **overrides,
    }


class TestFormatPublished(unittest.TestCase):
    def test_formats_utc_as_istanbul(self):
        item = _base_item()
        formatted = hg._format_published(item)
        self.assertIn("7 Ağustos 2026", formatted)
        # Istanbul is UTC+3 all year.
        self.assertIn("17:32", formatted)

    def test_missing_date_returns_empty(self):
        item = _base_item(published_at="", published="")
        self.assertEqual(hg._format_published(item), "")

    def test_invalid_date_returns_empty(self):
        item = _base_item(published_at="not a date")
        self.assertEqual(hg._format_published(item), "")


class TestEscape(unittest.TestCase):
    def test_escapes_html(self):
        self.assertEqual(hg._escape("<script>"), "&lt;script&gt;")
        self.assertEqual(hg._escape('"quoted"'), "&quot;quoted&quot;")
        self.assertEqual(hg._escape("a & b"), "a &amp; b")

    def test_none_returns_empty(self):
        self.assertEqual(hg._escape(None), "")


class TestGenerateNewsHtml(unittest.TestCase):
    def test_has_core_page_elements(self):
        output = hg.generate_news_html([_base_item()], {"toplam_haber": 1})
        self.assertIn("<!DOCTYPE html>", output)
        self.assertIn("AI News", output)
        self.assertIn("Bugünün Özeti", output)
        self.assertIn('id="home-search-input"', output)
        self.assertIn("category-filter-btn", output)
        self.assertIn("Reuters", output)
        self.assertIn("Ağustos 2026", output)

    def test_shows_source_and_published_date(self):
        output = hg.generate_news_html([_base_item()], {"toplam_haber": 1})
        self.assertIn("Reuters · 7 Ağustos 2026, 17:32", output)

    def test_escapes_user_content(self):
        malicious = "<script>alert(1)</script>"
        summary = 'Summary with "quotes" and ampersands & more'
        link = "http://example.com?a=1&b=2"
        items = [_base_item(title=malicious, summary=summary, link=link)]
        output = hg.generate_news_html(items, {"toplam_haber": 1})

        self.assertNotIn(malicious, output)
        self.assertIn("&lt;script&gt;", output)
        self.assertIn("&quot;", output)
        self.assertIn("&amp;", output)

    def test_links_have_safe_rel_and_target(self):
        output = hg.generate_news_html([_base_item()], {"toplam_haber": 1})
        self.assertIn('target="_blank"', output)
        self.assertIn('rel="noopener noreferrer"', output)

    def test_no_fake_date_when_missing(self):
        item = _base_item(published_at="", published="")
        output = hg.generate_news_html([item], {"toplam_haber": 1})
        self.assertIn("Reuters", output)
        self.assertNotIn("Reuters ·", output)

    def test_meta_line(self):
        item = _base_item()
        self.assertEqual(hg._meta_line(item), "Reuters · 7 Ağustos 2026, 17:32")

    def test_meta_line_without_date(self):
        item = _base_item(published_at="", published="")
        self.assertEqual(hg._meta_line(item), "Reuters")


class TestGenerateSearchHtml(unittest.TestCase):
    def test_embeds_search_data(self):
        index = [_base_item()]
        output = hg.generate_search_html(index)
        self.assertIn('id="search-input"', output)
        self.assertIn('id="search-results"', output)
        self.assertIn('id="search-data"', output)
        self.assertIn("OpenAI announces new model", output)

    def test_no_script_injection_in_search_data(self):
        index = [{"title": "</script><script>alert(1)</script>", "summary": "", "source": "X", "link": "#"}]
        output = hg.generate_search_html(index)
        self.assertNotIn("</script><script>", output)
        # The closing tag is escaped inside the JSON so it cannot break out of the script element.
        self.assertIn(r"<\/script>", output)


class TestAssets(unittest.TestCase):
    def test_css_and_js_non_empty(self):
        css = hg.get_css()
        js = hg.get_js()
        self.assertGreater(len(css), 500)
        self.assertGreater(len(js), 500)
        self.assertIn(".news-card", css)
        self.assertIn("newsCards", js)


if __name__ == "__main__":
    unittest.main()
