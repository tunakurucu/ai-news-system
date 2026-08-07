import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from services import story_clustering as sc


def _article(title, source="BBC Türkçe", category="dünya", importance=1, link="http://example.com", published_at="2026-08-07T14:00:00+00:00", summary="Summary text here"):
    return {
        "title": title,
        "summary": summary,
        "source": source,
        "link": link,
        "published_at": published_at,
        "published": published_at,
        "category": category,
        "importance_score": importance,
        "fetched_at": "2026-08-07T14:00:00+00:00",
    }


class TestStoryClustering(unittest.TestCase):
    def test_same_event_titles_group_into_one_story(self):
        articles = [
            _article("Menderes Belediye Başkanı Çiçek tutuklandı", source="TRT Haber"),
            _article("Menderes Belediye Başkanı İlkay Çiçek dahil 10 kişi tutuklandı", source="BBC Türkçe"),
        ]

        stories = sc.generate_stories(articles)
        self.assertEqual(len(stories), 1)
        self.assertEqual(stories[0]["article_count"], 2)
        self.assertEqual(stories[0]["source_count"], 2)
        self.assertIn("Menderes", stories[0]["canonical_title"])

    def test_unrelated_titles_remain_separate(self):
        articles = [
            _article("ABD-İran gerilimi yeniden tırmandı"),
            _article("Andy Burnham'ın İngiltere Başbakanı olması bekleniyor"),
            _article("Türkiye, Kıbrıs'ın kuzeyinde doğalgaz boru hattı inşa edecek"),
        ]

        stories = sc.generate_stories(articles)
        self.assertEqual(len(stories), 3)
        for story in stories:
            self.assertEqual(story["article_count"], 1)

    def test_story_id_is_deterministic(self):
        articles = [
            _article("Menderes Belediye Başkanı Çiçek tutuklandı"),
            _article("Menderes Belediye Başkanı İlkay Çiçek dahil 10 kişi tutuklandı"),
        ]

        run1 = sc.generate_stories(articles)
        run2 = sc.generate_stories(articles)
        self.assertEqual(run1[0]["story_id"], run2[0]["story_id"])

    def test_story_contains_all_underlying_articles(self):
        articles = [
            _article("Bakan Kurum: Devlet yönetmek ciddi bir iştir", source="TRT Haber"),
            _article("Bakan Kurum: Devlet yönetmek ciddi bir iştir, bu işler ahbap çavuş ilişkisiyle yürümez", source="Anadolu Ajansı"),
        ]

        stories = sc.generate_stories(articles)
        self.assertEqual(len(stories), 1)
        self.assertEqual(stories[0]["article_count"], 2)
        sources = {a["source"] for a in stories[0]["articles"]}
        self.assertEqual(sources, {"TRT Haber", "Anadolu Ajansı"})

    def test_canonical_metadata_derived_correctly(self):
        articles = [
            _article("A story title", importance=2, published_at="2026-08-07T12:00:00+00:00", source="BBC Türkçe"),
            _article("A story title from another source", importance=5, published_at="2026-08-07T10:00:00+00:00", source="TRT Haber"),
        ]

        stories = sc.generate_stories(articles)
        story = stories[0]
        self.assertEqual(story["importance_score"], 5)
        # Canonical title comes from the highest-importance article, which is first after sorting.
        self.assertIn("A story title", story["canonical_title"])
        # Representative published_at should be the earliest.
        self.assertEqual(story["published_at"], "2026-08-07T10:00:00+00:00")

    def test_clustering_is_conservative(self):
        # Same broad topic (Trump, Iran) but distinct events.
        articles = [
            _article("Trump: İran'ın nükleer silah edinmesi halinde akıl almaz sonuçlarla karşılaşacak"),
            _article("Trump'tan ABD Yüksek Mahkemesi kararına tepki: Mücadeleyi sürdüreceğim"),
        ]

        stories = sc.generate_stories(articles)
        # Both mention Trump but the second is about the Supreme Court, not Iran.
        self.assertEqual(len(stories), 2)

    def test_same_event_different_source_articles_merge(self):
        articles = [
            _article('Avcılar Belediyesine yönelik "ihaleye fesat karıştırma" soruşturmasında 12 şüpheli tutuklandı', source="Anadolu Ajansı"),
            _article("Avcılar Belediyesine yönelik soruşturmada 12 şüpheli tutuklandı", source="TRT Haber"),
        ]

        stories = sc.generate_stories(articles)
        self.assertEqual(len(stories), 1)
        self.assertEqual(stories[0]["source_count"], 2)

    def test_category_match_or_generic_allowed(self):
        articles = [
            _article("Menderes Belediye Başkanı Çiçek tutuklandı", category="genel"),
            _article("Menderes Belediye Başkanı İlkay Çiçek dahil 10 kişi tutuklandı", category="dünya"),
        ]

        stories = sc.generate_stories(articles)
        self.assertEqual(len(stories), 1)

    def test_different_categories_do_not_merge(self):
        articles = [
            _article("Dolar ve enflasyon beklentileri", category="ekonomi"),
            _article("Dolar ve enflasyon beklentileri", category="spor"),
        ]

        stories = sc.generate_stories(articles)
        self.assertEqual(len(stories), 2)

    def test_time_proximity_prevents_distant_matches(self):
        articles = [
            _article("Bakan Kurum açıklama yaptı", published_at="2026-08-07T10:00:00+00:00"),
            _article("Bakan Kurum açıklama yaptı", published_at="2026-08-01T10:00:00+00:00"),
        ]

        stories = sc.generate_stories(articles)
        # 6 days apart should exceed the 48-hour window.
        self.assertEqual(len(stories), 2)


class TestStoryClusteringRefinements(unittest.TestCase):
    def test_shared_topic_phrase_not_auto_merged(self):
        """Two different angles on a common topic phrase should stay separate."""
        articles = [
            _article("Mekke Savunma Anlaşması Türkiye'nin bölgedeki konumunu nasıl etkileyecek?", source="BBC Türkçe"),
            _article("Mekke Savunma Anlaşması bölgedeki güvenlik dengesini değiştirecek", source="TRT Haber"),
        ]

        stories = sc.generate_stories(articles)
        self.assertEqual(len(stories), 2)

    def test_same_event_menderes_still_merges(self):
        articles = [
            _article("Menderes Belediye Başkanı Çiçek tutuklandı", source="TRT Haber"),
            _article("Menderes Belediye Başkanı İlkay Çiçek dahil 10 kişi tutuklandı", source="BBC Türkçe"),
        ]

        stories = sc.generate_stories(articles)
        self.assertEqual(len(stories), 1)
        self.assertEqual(stories[0]["article_count"], 2)

    def test_same_event_avcilar_still_merges(self):
        articles = [
            _article('Avcılar Belediyesine yönelik "ihaleye fesat karıştırma" soruşturmasında 12 şüpheli tutuklandı', source="Anadolu Ajansı"),
            _article("Avcılar Belediyesine yönelik soruşturmada 12 şüpheli tutuklandı", source="TRT Haber"),
        ]

        stories = sc.generate_stories(articles)
        self.assertEqual(len(stories), 1)
        self.assertEqual(stories[0]["article_count"], 2)


if __name__ == "__main__":
    unittest.main()
