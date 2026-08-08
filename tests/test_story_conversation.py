import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from services import story_conversation as sc


def _make_article(source="BBC Türkçe", title="Title", summary="Summary text", link="http://example.com"):
    return {
        "source": source,
        "title": title,
        "summary": summary,
        "link": link,
        "published_at": "2026-08-07T14:00:00+00:00",
    }


def _make_story(articles, title="Story title", category="dünya"):
    return {
        "story_id": "abc123",
        "canonical_title": title,
        "category": category,
        "importance_score": 1,
        "published_at": "2026-08-07T14:00:00+00:00",
        "articles": articles,
        "brief_summary": "Kısa özet.",
        "detailed_summary": "Detaylı özet.",
        "key_facts": ["Fakt 1"],
        "why_it_matters": "Önemi.",
    }


def _mock_client(response_data):
    client = MagicMock()
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = json.dumps(response_data, ensure_ascii=False)
    response.choices[0].finish_reason = "stop"
    client.chat.completions.create.return_value = response
    return client


class TestStoryConversation(unittest.TestCase):
    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key"}, clear=False)
    def test_normal_grounded_question(self):
        story = _make_story([_make_article()])
        client = _mock_client({
            "answer": "Çünkü anlaşma metni böyle diyor.",
            "cited_sources": ["BBC Türkçe"],
        })

        result = sc.answer_question(story, "Neden önemli?", client=client)

        self.assertEqual(result["answer"], "Çünkü anlaşma metni böyle diyor.")
        self.assertEqual(result["citations"], [{"source": "BBC Türkçe", "title": "Title", "link": "http://example.com"}])

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key"}, clear=False)
    def test_follow_up_uses_history(self):
        story = _make_story([_make_article()])
        client = _mock_client({
            "answer": "Çünkü metin açık.",
            "cited_sources": ["BBC Türkçe"],
        })

        history = [
            {"role": "user", "content": "İlk soru"},
            {"role": "assistant", "content": "İlk cevap"},
        ]
        result = sc.answer_question(story, "peki neden?", history=history, client=client)

        self.assertEqual(result["answer"], "Çünkü metin açık.")
        call_args = client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1], history[0])
        self.assertEqual(messages[2], history[1])
        last = json.loads(messages[-1]["content"])
        self.assertEqual(last["question"], "peki neden?")
        self.assertIn("story", last)
        self.assertEqual(last["story"]["canonical_title"], "Story title")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key"}, clear=False)
    def test_multi_source_story(self):
        articles = [
            _make_article(source="BBC Türkçe", title="A", link="http://bbc.example"),
            _make_article(source="TRT Haber", title="B", link="http://trt.example"),
        ]
        story = _make_story(articles)
        client = _mock_client({
            "answer": "İki kaynak da aynı temel bilgiyi veriyor.",
            "cited_sources": ["BBC Türkçe", "TRT Haber"],
        })

        result = sc.answer_question(story, "İki kaynak aynı şeyi mi söylüyor?", client=client)

        sources = {c["source"] for c in result["citations"]}
        links = {c["link"] for c in result["citations"]}
        self.assertEqual(sources, {"BBC Türkçe", "TRT Haber"})
        self.assertEqual(links, {"http://bbc.example", "http://trt.example"})

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key"}, clear=False)
    def test_unsupported_question_insufficient_info(self):
        story = _make_story([_make_article()])
        client = _mock_client({
            "answer": "Mevcut kaynaklar bu soruyu yanıtlamak için yeterli bilgi içermiyor.",
            "cited_sources": [],
        })

        result = sc.answer_question(story, "Gelecekte ne olacak?", client=client)

        self.assertIn("Mevcut kaynaklar", result["answer"])
        self.assertEqual(result["citations"], [])

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key"}, clear=False)
    def test_api_failure_graceful_fallback(self):
        story = _make_story([_make_article()])
        client = MagicMock()
        client.chat.completions.create.side_effect = Exception("API failure")

        result = sc.answer_question(story, "Soru?", client=client)

        self.assertIn("yanıtlanamadı", result["answer"].lower())
        self.assertEqual(result["citations"], [])

    def test_missing_api_key_returns_fallback(self):
        env = os.environ.copy()
        env.pop("OPENAI_API_KEY", None)
        story = _make_story([_make_article()])

        with patch.dict(os.environ, env, clear=True):
            result = sc.answer_question(story, "Soru?")

        self.assertIn("API anahtarı", result["answer"])
        self.assertEqual(result["citations"], [])

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key"}, clear=False)
    def test_citations_derived_from_actual_articles(self):
        story = _make_story([_make_article(source="BBC Türkçe", link="http://real.example")])
        client = _mock_client({
            "answer": "Cevap.",
            "cited_sources": ["BBC Türkçe", "Uydurma Kaynak"],
        })

        result = sc.answer_question(story, "Soru?", client=client)

        self.assertEqual(len(result["citations"]), 1)
        self.assertEqual(result["citations"][0]["source"], "BBC Türkçe")
        self.assertEqual(result["citations"][0]["link"], "http://real.example")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key"}, clear=False)
    def test_empty_response_content_fallback(self):
        story = _make_story([_make_article()])
        client = MagicMock()
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = None
        response.choices[0].finish_reason = "length"
        client.chat.completions.create.return_value = response

        result = sc.answer_question(story, "Soru?", client=client)

        self.assertIn("boş yanıt", result["answer"])
        self.assertEqual(result["citations"], [])

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key"}, clear=False)
    def test_default_model_is_gpt5_mini_with_reasoning_tokens(self):
        story = _make_story([_make_article()])
        client = _mock_client({"answer": "Cevap.", "cited_sources": []})

        sc.answer_question(story, "Soru?", client=client)

        call_args = client.chat.completions.create.call_args
        self.assertEqual(call_args.kwargs["model"], "gpt-5-mini")
        self.assertEqual(call_args.kwargs["max_completion_tokens"], 4096)
        self.assertNotIn("temperature", call_args.kwargs)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key", "OPENAI_MODEL": "gpt-4o-mini"}, clear=False)
    def test_env_model_override_for_non_reasoning_model(self):
        story = _make_story([_make_article()])
        client = _mock_client({"answer": "Cevap.", "cited_sources": []})

        sc.answer_question(story, "Soru?", client=client)

        call_args = client.chat.completions.create.call_args
        self.assertEqual(call_args.kwargs["model"], "gpt-4o-mini")
        self.assertEqual(call_args.kwargs["max_completion_tokens"], 1024)
        self.assertEqual(call_args.kwargs["temperature"], 0.2)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key"}, clear=False)
    def test_system_prompt_forbids_outside_knowledge(self):
        prompt = sc._SYSTEM_PROMPT.lower()
        self.assertIn("dış bilgi", prompt)
        self.assertIn("tahmin", prompt)
        self.assertIn("mevcut kaynaklar", prompt)


if __name__ == "__main__":
    unittest.main()
