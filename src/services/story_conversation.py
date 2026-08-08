import json
import os

import openai

from services.story_synthesizer import (
    DEFAULT_MODEL,
    _create_client,
    _is_reasoning_model,
    _max_completion_tokens,
)
from utils.logger import get_logger

logger = get_logger()

_OUTPUT_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "story_qa",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "answer": {
                    "type": "string",
                    "description": (
                        "Kısa, doğal ve tarafsız Türkçe cevap. Kullanıcı daha fazla detay isterse daha uzun olabilir. "
                        "Yalnızca aşağıda sağlanan hikaye kaynaklarındaki bilgileri kullan. "
                        "Eğer kaynaklar soruyu yanıtlamak için yeterli değilse, 'Mevcut kaynaklar bu soruyu yanıtlamak için yeterli bilgi içermiyor.' şeklinde açıkça belirt."
                    ),
                },
                "cited_sources": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Cevapta kullanılan kaynakların adları. Sadece hikayedeki makalelerin 'source' alanında geçen, "
                        "doğrudan desteklediğin kaynakların adlarını listele. Uydurma kaynak veya URL ekleme."
                    ),
                },
            },
            "required": ["answer", "cited_sources"],
            "additionalProperties": False,
        },
    },
}

_SYSTEM_PROMPT = (
    "Sen dikkatli, tarafsız bir Türkçe haber asistanısın. "
    "Görevin: sana iletilen tek bir haber konusu (story) ve o konunun kaynak makaleleri üzerinden, "
    "kullanıcının sorduğu soruyu yanıtlamak.\n\n"
    "Kurallar:\n"
    "- Yalnızca aşağıda sağlanan hikaye metni ve ona ait makale özetlerini kullan. Dış bilgi, web araması, tahmin veya çıkarım ekleme.\n"
    "- Eksik bilgi varsa veya soru kaynaklarda yoksa 'Mevcut kaynaklar bu soruyu yanıtlamak için yeterli bilgi içermiyor.' de.\n"
    "- Kişi, kurum, tarih, sayı ve iddiaları olduğu gibi aktar; değiştirme.\n"
    "- Kaynaklar arasında önemli bir fark veya çelişki varsa belirt.\n"
    "- Cevabını kısa ve konuşma diline yakın tut. Kullanıcı 'biraz daha aç', 'detaylı anlat' gibi isterse daha açıklayıcı olabilir.\n"
    "- Kullanıcının niyet, motivasyon, strateji, amaç veya hislerini çıkarma.\n"
    "- Desteklenmeyen gelecekteki siyasi, sosyal, ekonomik, hukuki, güvenlik, sağlık veya pratik etkiler öne sürme.\n"
    "- Kaynakça olarak yalnızca hikayedeki makalelerin source adlarını kullan; uydurma kaynak veya URL ekleme.\n"
)


def _build_story_context(story):
    """Return a JSON-serializable summary of the selected story for the prompt."""
    return {
        "canonical_title": story.get("canonical_title", ""),
        "category": story.get("category", ""),
        "brief_summary": story.get("brief_summary", ""),
        "detailed_summary": story.get("detailed_summary", ""),
        "key_facts": story.get("key_facts", []),
        "why_it_matters": story.get("why_it_matters", ""),
        "articles": [
            {
                "source": a.get("source", ""),
                "title": a.get("title", ""),
                "summary": a.get("summary", ""),
                "published_at": a.get("published_at", ""),
            }
            for a in story.get("articles", [])
        ],
    }


def _resolve_citations(story, source_names):
    """Map source names returned by the model to actual article metadata."""
    articles = story.get("articles", [])
    known = {}
    for article in articles:
        source = article.get("source", "")
        if source and source not in known:
            known[source] = article

    citations = []
    seen = set()
    for name in source_names:
        if not isinstance(name, str) or not name:
            continue
        if name in seen:
            continue
        seen.add(name)
        article = known.get(name)
        if article is None:
            logger.warning(f"Model unknown source name in conversation citation: {name}")
            continue
        citations.append({
            "source": name,
            "title": article.get("title", ""),
            "link": article.get("link", ""),
        })
    return citations


def answer_question(story, question, history=None, model=None, client=None):
    """Answer a user question about a selected story using only its source material.

    Args:
        story: A story dict (e.g. from the output of story clustering/synthesis).
        question: The current user question as a string.
        history: Optional list of OpenAI-style message dicts representing the
            conversation so far (e.g. [{"role": "user", "content": ...},
            {"role": "assistant", "content": ...}]). The history is scoped to
            the same `story`; the service does not switch stories.
        model: Optional model name. Defaults to OPENAI_MODEL env var or gpt-5-mini.
        client: Optional OpenAI client for testing.

    Returns:
        A dict with "answer" (str) and "citations" (list of {source, title, link}).
        On failure or missing API key, returns a graceful fallback dict.
    """
    if client is None:
        client = _create_client()

    if client is None:
        logger.warning("OPENAI_API_KEY tanımlı değil; soru yanıtlanamıyor.")
        return {
            "answer": "Soru yanıtlanamadı: API anahtarı tanımlı değil.",
            "citations": [],
        }

    model = model or os.getenv("OPENAI_MODEL", DEFAULT_MODEL)

    user_content = {
        "story": _build_story_context(story),
        "question": question,
    }
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
    ]
    if history:
        messages.extend(history)
    messages.append(
        {"role": "user", "content": json.dumps(user_content, ensure_ascii=False, indent=2)},
    )

    create_params = {
        "model": model,
        "messages": messages,
        "response_format": _OUTPUT_SCHEMA,
        "max_completion_tokens": _max_completion_tokens(model),
    }
    # GPT-5 and o-series reasoning models do not support the temperature parameter.
    if not _is_reasoning_model(model):
        create_params["temperature"] = 0.2

    try:
        response = client.chat.completions.create(**create_params)
        message = response.choices[0].message
        finish_reason = getattr(response.choices[0], "finish_reason", None)
        raw = getattr(message, "content", None)
        if raw is None or raw == "":
            logger.error(
                f"OpenAI cevabı boş döndü (finish_reason={finish_reason}). "
                "Soru yanıtlanamıyor."
            )
            return {
                "answer": "Soru yanıtlanamadı: modelden boş yanıt alındı.",
                "citations": [],
            }
        parsed = json.loads(raw)
    except openai.APIError as e:
        logger.error(f"OpenAI API hatası: {e}")
        return {
            "answer": "Soru yanıtlanamadı: bir API hatası oluştu.",
            "citations": [],
        }
    except json.JSONDecodeError as e:
        logger.error(f"OpenAI cevabı JSON olarak ayrıştırılamadı: {e}")
        return {
            "answer": "Soru yanıtlanamadı: model yanıtı işlenemedi.",
            "citations": [],
        }
    except Exception as e:
        logger.error(f"Soru yanıtlanırken beklenmedik hata: {e}")
        return {
            "answer": "Soru yanıtlanamadı: beklenmedik bir hata oluştu.",
            "citations": [],
        }

    if "answer" not in parsed:
        logger.error("OpenAI cevabında 'answer' alanı eksik")
        return {
            "answer": "Soru yanıtlanamadı: model yanıtı eksik.",
            "citations": [],
        }

    answer = str(parsed.get("answer", "")).strip()
    cited_sources = parsed.get("cited_sources", [])
    if not isinstance(cited_sources, list):
        cited_sources = []

    citations = _resolve_citations(story, cited_sources)

    return {
        "answer": answer,
        "citations": citations,
    }
