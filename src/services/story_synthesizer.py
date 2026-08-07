import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import openai

from utils.file_helper import save_json
from utils.logger import get_logger

logger = get_logger()

DEFAULT_MODEL = "gpt-5-mini"
DEFAULT_MAX_TOKENS = 1024
REASONING_MAX_TOKENS = 4096
CACHE_VERSION = "2"
CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "cache" / "synthesis"


_OUTPUT_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "story_synthesis",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "brief_summary": {
                    "type": "string",
                    "description": "1-2 cümlelik özlü özet: ne oldu, temel bilgi.",
                },
                "detailed_summary": {
                    "type": "string",
                    "description": "Birkaç kısa paragrafta olay, bağlam ve kaynaklarda önemli ayrıntılar.",
                },
                "key_facts": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Olayın kendisine ait, kaynak metinlerde desteklenen 3-6 somut ve tekrar etmeyen bilgi noktası. Yalnızca yayın tarihi, kaynak adı, URL veya makale başlığı gibi meta verileri tekrar etme.",
                },
                "why_it_matters": {
                    "type": "string",
                    "description": "Gelişmenin pratik önemi; ancak kaynaklarda açıkça desteklenen veya doğrudan çıkarılabilir sonuçlar. Desteklenmeyen genel bilgi, tahmin veya spekülasyon ekleme. Kaynaklar anlamlı bir önem ifade etmiyorsa boş string döndür.",
                },
            },
            "required": ["brief_summary", "detailed_summary", "key_facts", "why_it_matters"],
            "additionalProperties": False,
        },
    },
}

_SYSTEM_PROMPT = (
    "Sen dikkatli, tarafsız ve özlü bir Türkçe haber editörüsün. "
    "Görevin: sana verilen haber kaynaklarını kullanarak tek bir olayı özetlemek.\n\n"
    "Kurallar:\n"
    "- Sadece sana iletilen kaynak metinleri kullan; dış bilgi, tahmin veya çıkarım ekleme.\n"
    "- Eksik bilgi varsa atla; uydurma.\n"
    "- Kişi, kurum, tarih, sayı ve iddiaları doğru aktar.\n"
    "- Kaynaklar arasında önemli bir fark veya çelişki varsa kısaca belirt.\n"
    "- brief_summary 1-2 cümle, detailed_summary birkaç kısa paragraf olsun.\n"
    "- key_facts 3-6 maddelik, OLAYIN KENDİSİNE ait somut ve tekrar etmeyen bilgi noktaları içersin. "
    "Yalnızca yayın tarihi, kaynak adı, URL veya makale başlığı gibi meta verileri tekrar etme; bunlar yalnızca haber değeri taşıdığında kullanılabilir.\n"
    "- why_it_matters bölümünde, kaynaklarda açıkça desteklenen veya doğrudan çıkarılabilir pratik önemi yaz. "
    "Desteklenmeyen genel bilgi, muhtemel ama kanıtlanmamış sonuç veya spekülatif siyasi/ekonomik/jeopolitik etki ekleme. "
    "Kaynaklar anlamlı bir önem ifade etmiyorsa, yalnızca verili gerçeklere dayanan çok kısa ve tutarlı bir ifade yaz; hiçbir şey yazamıyorsan boş string döndür.\n"
    "- Yazım tarzı: tarafsız, olgun, editoryal, gereksiz sıfat ve yapay dolgu cümlelerden kaçın.\n"
    "- Çıktı JSON formatında ve aşağıdaki alanları içermeli: brief_summary, detailed_summary, key_facts, why_it_matters.\n"
)


def _cache_key(story):
    """Deterministic cache key from story content and cache version."""
    payload = {
        "cache_version": CACHE_VERSION,
        "canonical_title": story.get("canonical_title", ""),
        "category": story.get("category", "genel"),
        "articles": [
            {
                "source": a.get("source", ""),
                "title": a.get("title", ""),
                "summary": a.get("summary", ""),
                "link": a.get("link", ""),
                "published_at": a.get("published_at", ""),
            }
            for a in story.get("articles", [])
        ],
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _cache_path(cache_dir, key):
    return Path(cache_dir or CACHE_DIR) / f"{key}.json"


def _read_cache(cache_dir, key):
    path = _cache_path(cache_dir, key)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Sentez önbelleği okunamadı: {e}")
        return None


def _write_cache(cache_dir, key, value):
    path = _cache_path(cache_dir, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    save_json(value, path)


def _derive_citations(story):
    """Build citations from the underlying articles."""
    citations = []
    seen = set()
    for article in story.get("articles", []):
        source = article.get("source", "")
        if source in seen:
            continue
        seen.add(source)
        citations.append({
            "source": source,
            "title": article.get("title", ""),
            "link": article.get("link", ""),
        })
    return citations


def _is_reasoning_model(model):
    """Return True for GPT-5 and o-series models that do not support temperature."""
    name = (model or "").lower()
    return name.startswith(("gpt-5", "o1", "o3", "o4"))


def _max_completion_tokens(model):
    """Return the completion-token budget appropriate for the model family."""
    return REASONING_MAX_TOKENS if _is_reasoning_model(model) else DEFAULT_MAX_TOKENS


def _build_messages(story):
    user_content = {
        "canonical_title": story.get("canonical_title", ""),
        "category": story.get("category", "genel"),
        "source_count": story.get("source_count", 1),
        "articles": [
            {
                "source": a.get("source", ""),
                "title": a.get("title", ""),
                "summary": a.get("summary", ""),
                "link": a.get("link", ""),
                "published_at": a.get("published_at", ""),
            }
            for a in story.get("articles", [])
        ],
    }
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(user_content, ensure_ascii=False, indent=2)},
    ]


def _create_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    return openai.OpenAI(max_retries=2)


def synthesize_story(story, model=None, client=None, cache_dir=None):
    """Synthesize one story, using cache and graceful fallback.

    Returns a new story dict with synthesis fields. If synthesis cannot be
    performed, the original story is returned unchanged.
    """
    key = _cache_key(story)
    cached = _read_cache(cache_dir, key)
    if cached is not None:
        logger.info(f"Önbellekten sentezlendi: {story.get('canonical_title', '')[:40]}...")
        new_story = dict(story)
        new_story.update(cached)
        new_story["citations"] = _derive_citations(story)
        new_story["synthesized_at"] = datetime.now(timezone.utc).isoformat()
        return new_story

    if client is None:
        client = _create_client()

    if client is None:
        logger.warning("OPENAI_API_KEY tanımlı değil; sentez atlanıyor.")
        return story

    model = model or os.getenv("OPENAI_MODEL", DEFAULT_MODEL)

    create_params = {
        "model": model,
        "messages": _build_messages(story),
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
                "Sentez atlanıyor."
            )
            return story
        parsed = json.loads(raw)
    except openai.APIError as e:
        logger.error(f"OpenAI API hatası: {e}")
        return story
    except json.JSONDecodeError as e:
        logger.error(f"OpenAI cevabı JSON olarak ayrıştırılamadı: {e}")
        return story
    except Exception as e:
        logger.error(f"Sentez sırasında beklenmedik hata: {e}")
        return story

    required = ("brief_summary", "detailed_summary", "key_facts", "why_it_matters")
    for field in required:
        if field not in parsed:
            logger.error(f"OpenAI cevabında eksik alan: {field}")
            return story

    if not isinstance(parsed.get("key_facts"), list):
        logger.error("OpenAI cevabında key_facts bir liste değil")
        return story

    synthesis = {
        "brief_summary": str(parsed["brief_summary"]).strip(),
        "detailed_summary": str(parsed["detailed_summary"]).strip(),
        "key_facts": [str(f).strip() for f in parsed["key_facts"] if str(f).strip()],
        "why_it_matters": str(parsed["why_it_matters"]).strip(),
    }

    _write_cache(cache_dir, key, synthesis)

    new_story = dict(story)
    new_story.update(synthesis)
    new_story["citations"] = _derive_citations(story)
    new_story["synthesized_at"] = datetime.now(timezone.utc).isoformat()
    return new_story


def synthesize_stories(stories, model=None, client=None, cache_dir=None):
    """Synthesize a list of stories, skipping any that fail.

    One API call per story at most. The rest of the pipeline continues even
    if individual synthesis calls fail.
    """
    if client is None and not os.getenv("OPENAI_API_KEY"):
        logger.info("OPENAI_API_KEY tanımlı değil; hikaye sentezi atlanıyor.")
        return stories

    if client is None:
        client = openai.OpenAI(max_retries=2)

    results = []
    for story in stories:
        try:
            results.append(synthesize_story(story, model=model, client=client, cache_dir=cache_dir))
        except Exception as e:
            logger.error(f"Hikaye sentezlenirken hata: {e}")
            results.append(story)
    return results
