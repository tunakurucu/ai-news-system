import json
import os
import sys
import tempfile
import unittest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from services import story_synthesizer as ss


@contextmanager
def _temp_cache():
    with tempfile.TemporaryDirectory() as tmp:
        yield tmp


def _make_article(source="BBC Türkçe", title="Title", summary="Summary text", link="http://example.com"):
    return {
        "source": source,
        "title": title,
        "summary": summary,
        "link": link,
        "published_at": "2026-08-07T14:00:00+00:00",
        "published": "2026-08-07T14:00:00+00:00",
    }


def _make_story(articles, title="Story title", category="dünya"):
    return {
        "story_id": "abc123",
        "canonical_title": title,
        "category": category,
        "importance_score": 1,
        "published_at": "2026-08-07T14:00:00+00:00",
        "articles": articles,
        "article_count": len(articles),
        "source_count": len({a["source"] for a in articles}),
    }


def _mock_client(response_data):
    client = MagicMock()
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = json.dumps(response_data, ensure_ascii=False)
    client.chat.completions.create.return_value = response
    return client


class TestSynthesizeStory(unittest.TestCase):
    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key"}, clear=False)
    def test_synthesized_story_has_expected_fields(self):
        story = _make_story([_make_article()])
        client = _mock_client({
            "brief_summary": "Kısa özet.",
            "detailed_summary": "Detaylı özet.",
            "key_facts": ["Fakt 1", "Fakt 2"],
            "why_it_matters": "Önemi.",
        })

        with _temp_cache() as cache_dir:
            result = ss.synthesize_story(story, client=client, cache_dir=cache_dir)

        self.assertEqual(result["brief_summary"], "Kısa özet.")
        self.assertEqual(result["detailed_summary"], "Detaylı özet.")
        self.assertEqual(result["key_facts"], ["Fakt 1", "Fakt 2"])
        self.assertEqual(result["why_it_matters"], "Önemi.")
        self.assertEqual(result["citations"], [{"source": "BBC Türkçe", "title": "Title", "link": "http://example.com"}])
        self.assertIn("synthesized_at", result)
        # Underlying articles must remain intact.
        self.assertEqual(result["articles"], story["articles"])

    def test_missing_api_key_returns_story_unchanged(self):
        env = os.environ.copy()
        env.pop("OPENAI_API_KEY", None)
        with patch.dict(os.environ, env, clear=True):
            story = _make_story([_make_article()])
            result = ss.synthesize_story(story)

        self.assertEqual(result, story)
        self.assertNotIn("brief_summary", result)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key"}, clear=False)
    def test_api_error_does_not_break_pipeline(self):
        story = _make_story([_make_article()])
        client = MagicMock()
        client.chat.completions.create.side_effect = Exception("API failure")

        with _temp_cache() as cache_dir:
            result = ss.synthesize_story(story, client=client, cache_dir=cache_dir)
        self.assertEqual(result, story)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key"}, clear=False)
    def test_malformed_json_returns_story_unchanged(self):
        story = _make_story([_make_article()])
        client = MagicMock()
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = "not valid json"
        client.chat.completions.create.return_value = response

        with _temp_cache() as cache_dir:
            result = ss.synthesize_story(story, client=client, cache_dir=cache_dir)
        self.assertEqual(result, story)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key"}, clear=False)
    def test_cache_avoids_duplicate_api_call(self):
        story = _make_story([_make_article()])
        client = _mock_client({
            "brief_summary": "Kısa.",
            "detailed_summary": "Detay.",
            "key_facts": ["Fakt"],
            "why_it_matters": "Önem.",
        })

        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = tmp
            ss.synthesize_story(story, client=client, cache_dir=cache_dir)
            # Second call with a different client should not call the API.
            client2 = MagicMock()
            client2.chat.completions.create.side_effect = Exception("should not be called")
            result = ss.synthesize_story(story, client=client2, cache_dir=cache_dir)

        self.assertEqual(result["brief_summary"], "Kısa.")
        client2.chat.completions.create.assert_not_called()

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key"}, clear=False)
    def test_single_source_story(self):
        story = _make_story([_make_article(source="BBC Türkçe")])
        client = _mock_client({
            "brief_summary": "Bir kaynak.",
            "detailed_summary": "Detay.",
            "key_facts": ["Fakt"],
            "why_it_matters": "Önem.",
        })
        with _temp_cache() as cache_dir:
            result = ss.synthesize_story(story, client=client, cache_dir=cache_dir)
        self.assertEqual(len(result["citations"]), 1)
        self.assertEqual(result["citations"][0]["source"], "BBC Türkçe")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key"}, clear=False)
    def test_multi_source_story_passes_all_articles(self):
        articles = [
            _make_article(source="BBC Türkçe", title="A"),
            _make_article(source="TRT Haber", title="B"),
        ]
        story = _make_story(articles)
        client = _mock_client({
            "brief_summary": "Çoklu kaynak.",
            "detailed_summary": "Detay.",
            "key_facts": ["Fakt"],
            "why_it_matters": "Önem.",
        })

        with _temp_cache() as cache_dir:
            result = ss.synthesize_story(story, client=client, cache_dir=cache_dir)
        # Citations are derived from the underlying articles.
        sources = {c["source"] for c in result["citations"]}
        self.assertEqual(sources, {"BBC Türkçe", "TRT Haber"})
        # The prompt should include both articles. Inspect call args.
        call_args = client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        user_content = json.loads(messages[1]["content"])
        self.assertEqual(len(user_content["articles"]), 2)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key"}, clear=False)
    def test_synthesize_stories_runs_each_story(self):
        stories = [
            _make_story([_make_article()], title="Story 1"),
            _make_story([_make_article()], title="Story 2"),
        ]
        client = _mock_client({
            "brief_summary": "Kısa.",
            "detailed_summary": "Detay.",
            "key_facts": ["Fakt"],
            "why_it_matters": "Önem.",
        })

        with _temp_cache() as cache_dir:
            results = ss.synthesize_stories(stories, client=client, cache_dir=cache_dir)
        self.assertEqual(len(results), 2)
        for r in results:
            self.assertIn("brief_summary", r)

    def test_synthesize_stories_no_key_returns_original(self):
        env = os.environ.copy()
        env.pop("OPENAI_API_KEY", None)
        stories = [_make_story([_make_article()])]
        with patch.dict(os.environ, env, clear=True):
            results = ss.synthesize_stories(stories)
        self.assertEqual(results, stories)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key"}, clear=False)
    def test_empty_response_content_returns_story_unchanged(self):
        story = _make_story([_make_article()])
        client = MagicMock()
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = None
        response.choices[0].finish_reason = "length"
        client.chat.completions.create.return_value = response

        with _temp_cache() as cache_dir:
            result = ss.synthesize_story(story, client=client, cache_dir=cache_dir)
        self.assertEqual(result, story)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key"}, clear=False)
    def test_reasoning_model_uses_higher_completion_budget(self):
        story = _make_story([_make_article()])
        client = _mock_client({
            "brief_summary": "Kısa.",
            "detailed_summary": "Detay.",
            "key_facts": ["Fakt"],
            "why_it_matters": "Önem.",
        })

        with _temp_cache() as cache_dir:
            ss.synthesize_story(story, model="gpt-5-mini", client=client, cache_dir=cache_dir)

        call_args = client.chat.completions.create.call_args
        self.assertEqual(call_args.kwargs["max_completion_tokens"], 4096)
        self.assertNotIn("temperature", call_args.kwargs)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key"}, clear=False)
    def test_non_reasoning_model_uses_lower_completion_budget(self):
        story = _make_story([_make_article()])
        client = _mock_client({
            "brief_summary": "Kısa.",
            "detailed_summary": "Detay.",
            "key_facts": ["Fakt"],
            "why_it_matters": "Önem.",
        })

        with _temp_cache() as cache_dir:
            ss.synthesize_story(story, model="gpt-4o-mini", client=client, cache_dir=cache_dir)

        call_args = client.chat.completions.create.call_args
        self.assertEqual(call_args.kwargs["max_completion_tokens"], 1024)
        self.assertEqual(call_args.kwargs["temperature"], 0.2)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key"}, clear=False)
    def test_cache_key_changes_with_version(self):
        story = _make_story([_make_article()])

        original_version = ss.CACHE_VERSION
        try:
            ss.CACHE_VERSION = "v1"
            key_v1 = ss._cache_key(story)
            ss.CACHE_VERSION = "v2"
            key_v2 = ss._cache_key(story)
        finally:
            ss.CACHE_VERSION = original_version

        self.assertNotEqual(key_v1, key_v2)


if __name__ == "__main__":
    unittest.main()
