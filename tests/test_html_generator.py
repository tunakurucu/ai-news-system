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
    def test_shows_source_and_published_date(self):
        items = [_base_item()]
        output = hg.generate_news_html(items, {"toplam_haber": 1})
        self.assertIn("Reuters", output)
        self.assertIn("7 Ağustos 2026", output)
        self.assertIn("17:32", output)

    def test_escapes_user_content(self):
        malicious = "<script>alert(1)</script>"
        summary = 'Summary with "quotes" and ampersands & more'
        link = "http://example.com?a=1&b=2"
        items = [_base_item(title=malicious, summary=summary, link=link)]
        output = hg.generate_news_html(items, {"toplam_haber": 1})

        self.assertNotIn(malicious, output)
        self.assertIn("<h3>&lt;script&gt;alert(1)&lt;/script&gt;</h3>", output)
        self.assertIn("&quot;", output)
        self.assertIn("&amp;", output)
        # Escaped ampersands appear in the href; the link is still browser-safe.
        self.assertIn("http://example.com?a=1&amp;b=2", output)

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


if __name__ == "__main__":
    unittest.main()
