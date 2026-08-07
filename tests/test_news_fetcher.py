import os
import sys
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from services import news_fetcher as nf


class TestParsePublishedDatetime(unittest.TestCase):
    def test_parsed_tuple_returns_iso(self):
        entry = {
            "published_parsed": (2026, 8, 7, 14, 32, 0, 0, 0, 0),
            "published": "Fri, 07 Aug 2026 14:32:00 +0000",
        }
        dt, iso = nf._parse_published_datetime(entry)
        self.assertIsNotNone(dt)
        self.assertEqual(iso, "2026-08-07T14:32:00+00:00")
        self.assertEqual(dt.tzinfo, timezone.utc)

    def test_updated_parsed_fallback(self):
        entry = {
            "updated_parsed": (2026, 8, 7, 10, 0, 0, 0, 0, 0),
        }
        dt, iso = nf._parse_published_datetime(entry)
        self.assertIsNotNone(dt)
        self.assertEqual(iso, "2026-08-07T10:00:00+00:00")

    def test_iso_string(self):
        entry = {"published": "2026-08-07T14:32:00Z"}
        dt, iso = nf._parse_published_datetime(entry)
        self.assertIsNotNone(dt)
        self.assertEqual(iso, "2026-08-07T14:32:00+00:00")

    def test_invalid_date(self):
        entry = {"published": "not a date"}
        dt, iso = nf._parse_published_datetime(entry)
        self.assertIsNone(dt)
        self.assertEqual(iso, "")

    def test_missing_date(self):
        entry = {"title": "no date"}
        dt, iso = nf._parse_published_datetime(entry)
        self.assertIsNone(dt)
        self.assertEqual(iso, "")


class TestEntryToNews(unittest.TestCase):
    def test_maps_fields(self):
        entry = {
            "title": "Title",
            "summary": "Summary text",
            "link": "http://example.com",
            "published": "Fri, 07 Aug 2026 14:32:00 +0000",
            "published_parsed": (2026, 8, 7, 14, 32, 0, 0, 0, 0),
        }
        result = nf._entry_to_news(entry, "BBC Türkçe", "2026-08-07T19:35:00+00:00")
        self.assertEqual(result["source"], "BBC Türkçe")
        self.assertEqual(result["title"], "Title")
        self.assertEqual(result["published"], "Fri, 07 Aug 2026 14:32:00 +0000")
        self.assertEqual(result["published_at"], "2026-08-07T14:32:00+00:00")
        self.assertEqual(result["fetched_at"], "2026-08-07T19:35:00+00:00")

    def test_missing_published(self):
        entry = {"title": "No date"}
        result = nf._entry_to_news(entry, "Test", "2026-08-07T19:35:00+00:00")
        self.assertEqual(result["published"], "")
        self.assertEqual(result["published_at"], "")


class TestFetchNews(unittest.TestCase):
    @patch("services.news_fetcher.load_rss_sources")
    @patch("services.news_fetcher.feedparser.parse")
    def test_one_failed_feed_does_not_block_others(self, mock_parse, mock_load):
        mock_load.return_value = [
            {"name": "Bad Feed", "url": "http://bad.example/rss"},
            {"name": "Good Feed", "url": "http://good.example/rss"},
        ]

        def parse_side_effect(url):
            if "bad" in url:
                raise ConnectionError("timeout")
            return {
                "entries": [
                    {
                        "title": "Good Title That Is Long Enough",
                        "summary": "This summary is longer than thirty characters.",
                        "link": "http://example.com/good",
                        "published_parsed": (2026, 8, 7, 14, 32, 0, 0, 0, 0),
                    }
                ]
            }

        mock_parse.side_effect = parse_side_effect

        result = nf.fetch_news(limit_per_source=1)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["source"], "Good Feed")
        self.assertEqual(result[0]["published_at"], "2026-08-07T14:32:00+00:00")

    @patch("services.news_fetcher.load_rss_sources")
    @patch("services.news_fetcher.feedparser.parse")
    def test_empty_malformed_feed_is_skipped(self, mock_parse, mock_load):
        mock_load.return_value = [
            {"name": "Empty", "url": "http://empty.example/rss"},
        ]
        mock_parse.return_value = {
            "bozo": True,
            "bozo_exception": Exception("bad xml"),
            "entries": [],
        }

        result = nf.fetch_news(limit_per_source=1)
        self.assertEqual(result, [])

if __name__ == "__main__":
    unittest.main()
