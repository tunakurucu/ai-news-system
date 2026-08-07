import hashlib
import re
from datetime import datetime, timezone, timedelta

_STORY_ID_SALT = "ai-news-story"

_TURKISH_STOPWORDS = {
    "bir", "bu", "şu", "o", "ve", "ile", "için", "de", "da", "ki", "mi",
    "kadar", "gibi", "çok", "daha", "en", "her", "bütün", "tüm", "sonra",
    "önce", "ise", "ya", "eğer", "a", "the", "of", "to", "in", "and", "is", "on",
    "ile", "tarafından", "kendi", "buna", "göre", "yeni", "ilk", "iki", "üç",
}

_MAX_CLUSTER_HOURS = 48


def _normalize_text(text):
    """Lowercase, strip punctuation, collapse whitespace."""
    if not text:
        return ""
    text = str(text).lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _tokens(text):
    """Return a set of meaningful tokens."""
    normalized = _normalize_text(text)
    words = [w for w in normalized.split() if w and w not in _TURKISH_STOPWORDS and len(w) > 2]
    return set(words)


def _parse_datetime(raw):
    """Parse a date string into a timezone-aware UTC datetime."""
    if not raw:
        return None
    raw = str(raw).strip()
    if not raw:
        return None

    # ISO 8601 / RFC 3339
    try:
        iso = raw
        if iso.endswith("Z"):
            iso = iso[:-1] + "+00:00"
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass

    # RFC 2822 / email-style
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass

    return None


def _get_published_at(item):
    """Return a normalized ISO 8601 date string for an item, or empty."""
    raw = item.get("published_at") or item.get("published") or ""
    dt = _parse_datetime(raw)
    if dt:
        return dt.isoformat()
    return str(raw).strip()


def _article_datetime(item):
    """Return a datetime object for an item, or None."""
    raw = item.get("published_at") or item.get("published") or ""
    return _parse_datetime(raw)


def _jaccard(a, b):
    """Jaccard similarity of two sets, 0.0 to 1.0."""
    if not a or not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _token_list(text):
    """Return an ordered list of meaningful tokens."""
    normalized = _normalize_text(text)
    return [w for w in normalized.split() if w and w not in _TURKISH_STOPWORDS and len(w) > 2]


def _has_common_ngram(tokens_a, tokens_b, n=3):
    """Return True if two ordered token lists share a contiguous n-gram."""
    if len(tokens_a) < n or len(tokens_b) < n:
        return False
    ngrams_a = {" ".join(tokens_a[i : i + n]) for i in range(len(tokens_a) - n + 1)}
    ngrams_b = {" ".join(tokens_b[i : i + n]) for i in range(len(tokens_b) - n + 1)}
    return bool(ngrams_a & ngrams_b)


def _title_similarity(title_a, title_b):
    """Conservative deterministic similarity between two titles."""
    norm_a = _normalize_text(title_a)
    norm_b = _normalize_text(title_b)

    if not norm_a or not norm_b:
        return 0.0

    # Exact normalized match is the strongest signal.
    if norm_a == norm_b:
        return 1.0

    tokens_a = _tokens(title_a)
    tokens_b = _tokens(title_b)
    list_a = _token_list(title_a)
    list_b = _token_list(title_b)

    if not tokens_a or not tokens_b:
        return 0.0

    # Token overlap and Jaccard score.
    overlap = len(tokens_a & tokens_b)
    jaccard = _jaccard(tokens_a, tokens_b)

    # High overlap with enough shared words is a strong signal.
    if overlap >= 5 and jaccard >= 0.45:
        return jaccard

    # Moderate overlap: still likely related, but require a decent Jaccard.
    if overlap >= 4 and jaccard >= 0.55:
        return jaccard

    # A shared contiguous 3-gram is a useful phrase signal, but only when there is
    # also meaningful overall token overlap. This prevents a common topic phrase
    # (e.g. "Mekke Savunma Anlaşması") from merging different angles on the same topic.
    if _has_common_ngram(list_a, list_b, n=3) and overlap >= 5 and jaccard >= 0.40:
        return jaccard

    # If one title's tokens are a subset of the other, they likely describe the same story.
    smaller = tokens_a if len(tokens_a) <= len(tokens_b) else tokens_b
    larger = tokens_b if smaller is tokens_a else tokens_a
    if smaller.issubset(larger) and len(smaller) >= 4:
        return 0.9

    return 0.0


def _category_compatible(cat_a, cat_b):
    """Allow clustering across generic 'genel' and matching concrete categories."""
    if cat_a == cat_b:
        return True
    if cat_a == "genel" or cat_b == "genel":
        return True
    return False


def _time_compatible(a, b):
    """Require articles to be within a reasonable time window when dates are known."""
    dt_a = _article_datetime(a)
    dt_b = _article_datetime(b)
    if dt_a is None or dt_b is None:
        return True
    return abs(dt_a - dt_b) <= timedelta(hours=_MAX_CLUSTER_HOURS)


def _make_story_id(canonical_title, category):
    """Return a deterministic, stable story ID based on canonical content."""
    normalized = _normalize_text(canonical_title)
    seed = f"{_STORY_ID_SALT}|{category}|{normalized}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def _article_copy(item):
    """Return a clean article representation for the story."""
    return {
        "source": item.get("source", ""),
        "title": item.get("title", ""),
        "summary": item.get("summary", ""),
        "link": item.get("link", ""),
        "published": item.get("published", ""),
        "published_at": _get_published_at(item),
    }


def _sort_articles(articles):
    """Deterministically order articles before clustering."""
    def sort_key(item):
        score = item.get("importance_score", 0)
        dt = _article_datetime(item) or datetime.max.replace(tzinfo=timezone.utc)
        link = item.get("link", "")
        return (-score, dt, link)

    return sorted(articles, key=sort_key)


def _find_best_story(article, stories):
    """Find the most similar existing story for an article, or None."""
    best_story = None
    best_score = 0.0
    # 3-gram matches can merge at a slightly lower Jaccard floor when there is
    # also meaningful overlap (>=5 tokens). Non-phrase matches still need >=0.45.
    score_threshold = 0.40

    for story in stories:
        if not _category_compatible(article.get("category", "genel"), story.get("category", "genel")):
            continue

        # Compare the new article to the canonical title and all existing story articles.
        candidates = [story.get("canonical_title", "")]
        candidates.extend([a.get("title", "") for a in story.get("articles", [])])

        for candidate in candidates:
            score = _title_similarity(article.get("title", ""), candidate)
            if score > best_score and _time_compatible(article, story):
                best_score = score
                best_story = story

    if best_score >= score_threshold:
        return best_story
    return None


def _update_story(story, article):
    """Add an article to an existing story and refresh derived metadata."""
    story["articles"].append(_article_copy(article))
    story["article_count"] = len(story["articles"])

    sources = {a.get("source", "") for a in story["articles"]}
    story["source_count"] = len(sources)

    article_score = article.get("importance_score", 0) or 0
    if article_score > story.get("importance_score", 0):
        story["importance_score"] = article_score

    article_dt = _article_datetime(article)
    story_dt = _parse_datetime(story.get("published_at", ""))
    if article_dt and (story_dt is None or article_dt < story_dt):
        story["published_at"] = article_dt.isoformat()


def _new_story(article):
    """Create a new story from an article."""
    canonical_title = article.get("title", "") or ""
    category = article.get("category", "genel")
    story_id = _make_story_id(canonical_title, category)
    published_at = _get_published_at(article)

    return {
        "story_id": story_id,
        "canonical_title": canonical_title,
        "category": category,
        "importance_score": article.get("importance_score", 0) or 0,
        "published_at": published_at,
        "articles": [_article_copy(article)],
        "article_count": 1,
        "source_count": 1,
    }


def cluster_articles(articles):
    """Group articles into stories using deterministic, conservative clustering.

    Clustering rules:
      - exact normalized title match
      - one title's tokens are a subset of the other's (>= 4 tokens)
      - Jaccard similarity >= 0.45 with enough shared tokens
      - categories must match or one is 'genel'
      - when both articles have dates, they must be within 48 hours
    """
    sorted_articles = _sort_articles(articles)
    stories = []

    for article in sorted_articles:
        story = _find_best_story(article, stories)
        if story:
            _update_story(story, article)
        else:
            stories.append(_new_story(article))

    # Deterministic final ordering.
    def story_key(story):
        dt = _parse_datetime(story.get("published_at", ""))
        return (
            -story.get("importance_score", 0),
            dt or datetime.max.replace(tzinfo=timezone.utc),
            story.get("story_id", ""),
        )

    return sorted(stories, key=story_key)


def generate_stories(news_items):
    """Generate a list of story objects from categorized/filtered articles."""
    return cluster_articles(news_items)
