"""
Spotify Review Discovery Engine - Scraper & Analysis Tests
"""

import sys
import unittest
import pandas as pd
from unittest.mock import patch, MagicMock

sys.path.insert(0, ".")

from config import settings
from scrapers.base_scraper import BaseScraper
from scrapers.playstore_scraper import PlayStoreScraper
from analysis.sentiment import SentimentAnalyzer
from analysis.theme_classifier import ThemeClassifier
from utils.data_io import (
    restore_analyzed_dataframe,
    save_analyzed_data,
    load_analyzed_data,
    export_analyzed_dataframe_to_excel,
)
import tempfile
import os


class TestScrapersAndAnalysis(unittest.TestCase):
    """Verifies scrapers output schema and analysis modules output correct structures."""

    def test_base_scraper_schema(self) -> None:
        """Verifies base scraper produces an empty DataFrame with the correct schema."""
        class DummyScraper(BaseScraper):
            def scrape(self) -> pd.DataFrame:
                return self._create_empty_dataframe()

        scraper = DummyScraper()
        df = scraper.scrape()
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(list(df.columns), settings.STANDARD_COLUMNS)

    @patch("google_play_scraper.reviews")
    def test_playstore_scraper(self, mock_reviews: MagicMock) -> None:
        """Verifies PlayStoreScraper mock extraction works and maps fields correctly."""
        # Mock Google Play API response
        mock_reviews.return_value = (
            [
                {
                    "content": "This is a play store review about discovery weekly",
                    "score": 4,
                    "at": pd.Timestamp("2026-06-20").to_pydatetime(),
                    "userName": "tester1",
                    "thumbsUpCount": 12,
                    "reviewCreatedVersion": "8.8.8.8",
                }
            ],
            "some_token",
        )

        scraper = PlayStoreScraper(count=1)
        with patch.object(scraper, "_notify_progress"):
            df = scraper.scrape()
            self.assertFalse(df.empty)
            self.assertEqual(len(df), 1)
            self.assertEqual(df.iloc[0]["source"], "Google Play Store")
            self.assertEqual(df.iloc[0]["review_text"], "This is a play store review about discovery weekly")
            self.assertEqual(df.iloc[0]["rating"], 4)
            self.assertEqual(df.iloc[0]["username"], "tester1")

    def test_sentiment_analyzer(self) -> None:
        """Tests SentimentAnalyzer maps correct sentiment labels."""
        analyzer = SentimentAnalyzer()
        test_df = pd.DataFrame(
            {
                "review_text": [
                    "I love the new Discover Weekly recommendations, it is excellent!",
                    "This Spotify update is horrible, I hate the recommendation algorithm.",
                    "I listened to some music today.",
                ]
            }
        )
        res = analyzer.analyze(test_df)
        self.assertIn("sentiment_label", res.columns)
        self.assertIn("sentiment_compound", res.columns)
        
        # Verify labels match compound thresholds roughly
        self.assertEqual(res.iloc[0]["sentiment_label"], "Positive")
        self.assertEqual(res.iloc[1]["sentiment_label"], "Negative")
        self.assertEqual(res.iloc[2]["sentiment_label"], "Neutral")

    def test_theme_classifier(self) -> None:
        """Tests ThemeClassifier tags correct keywords according to taxonomy."""
        classifier = ThemeClassifier()
        test_df = pd.DataFrame(
            {
                "review_text": [
                    "The algorithm keeps playing the same songs on repeat.",
                    "I premium paid cost subscription update is nice.",
                ]
            }
        )
        res = classifier.analyze(test_df)
        
        # Verify theme columns are created
        self.assertTrue(res.iloc[0]["theme_Discovery Frustrations"])
        self.assertTrue(res.iloc[0]["theme_Algorithm Complaints"])
        self.assertTrue(res.iloc[1]["theme_Premium vs Free"])

    def test_csv_type_restoration(self) -> None:
        """Verifies analyzed CSV round-trip restores boolean and list columns."""
        classifier = ThemeClassifier()
        analyzed = classifier.analyze(
            pd.DataFrame({"review_text": ["The algorithm keeps playing the same songs on repeat."]})
        )
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            path = tmp.name
        try:
            save_analyzed_data(analyzed, path)
            loaded = load_analyzed_data(path)
            self.assertTrue(loaded.iloc[0]["theme_Discovery Frustrations"])
            self.assertIsInstance(loaded.iloc[0]["themes"], list)
        finally:
            os.unlink(path)

    def test_excel_export(self) -> None:
        """Verifies analyzed data can be exported as a valid Excel workbook."""
        classifier = ThemeClassifier()
        analyzed = classifier.analyze(
            pd.DataFrame({"review_text": ["The algorithm keeps playing the same songs on repeat."]})
        )
        excel_bytes = export_analyzed_dataframe_to_excel(analyzed)
        self.assertIsInstance(excel_bytes, bytes)
        self.assertGreater(len(excel_bytes), 0)
        self.assertEqual(excel_bytes[:2], b"PK")

    def test_reddit_rss_parser(self) -> None:
        """Verifies Reddit RSS Atom entries are parsed into review rows."""
        from scrapers.reddit_scraper import RedditScraper

        sample = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Spotify discovery is broken</title>
    <updated>2026-05-15T09:13:05+00:00</updated>
    <author><name>/u/tester</name></author>
    <content type="html">&lt;p&gt;Same songs every week&lt;/p&gt;</content>
  </entry>
</feed>"""
        scraper = RedditScraper()
        records = scraper._parse_rss_entries(sample)
        self.assertEqual(len(records), 1)
        self.assertIn("discovery", records[0]["review_text"].lower())
        self.assertEqual(records[0]["source"], "Reddit")

    def test_community_recent_posts_parser(self) -> None:
        """Verifies community recent-post rows are parsed with dates."""
        from scrapers.community_scraper import CommunityForumScraper
        from bs4 import BeautifulSoup

        html = """
        <table>
          <tr class="lia-list-row">
            <td>
              <h2 class="message-subject">
                <a class="page-link" href="/t5/example">Discover weekly repeats songs-(<span class="DateTime"><span class="local-friendly-date" title="2026-06-21 11:31 PM">22m ago</span></span>)</a>
              </h2>
              <div class="message-subject-body">I keep hearing the same tracks in Discover Weekly.</div>
              <span class="UserName"><a title="testuser">testuser</a></span>
            </td>
          </tr>
        </table>
        """
        scraper = CommunityForumScraper()
        row = BeautifulSoup(html, "html.parser").select_one("tr.lia-list-row")
        record = scraper._parse_list_row(row)
        self.assertIsNotNone(record)
        assert record is not None
        self.assertIn("Discover weekly", record["review_text"])
        self.assertEqual(record["date"], "2026-06-21 11:31 PM")

    def test_normalize_date_column(self) -> None:
        """Verifies mixed date formats normalize for trend charts."""
        from utils.data_io import normalize_date_column

        df = normalize_date_column(
            pd.DataFrame(
                {
                    "date": [
                        "2026-05-15T09:13:05+00:00",
                        "\u200e2026-06-21 11:31 PM",
                        "invalid",
                    ]
                }
            )
        )
        self.assertEqual(int(df["date"].notna().sum()), 2)

    def test_insights_excel_export(self) -> None:
        """Verifies strategic insights export produces a valid workbook."""
        from utils.data_io import export_insights_to_excel

        classifier = ThemeClassifier()
        analyzed = classifier.analyze(
            pd.DataFrame({"review_text": ["The algorithm keeps playing the same songs on repeat."]})
        )
        insights = [
            {
                "question": "Why do users struggle to discover new music?",
                "problem_statement": "Users feel they are not discovering enough new music.",
                "summary": "Sample summary.",
                "key_stats": {
                    "total_relevant_reviews": 1,
                    "pct_of_total": 100,
                    "pct_of_negative": 100,
                },
                "segment_breakdown": [{"name": "Low-rating app store users", "negative_review_count": 1}],
            }
        ]
        excel_bytes = export_insights_to_excel(
            analyzed,
            insights,
            {"key_findings": ["Finding one."]},
        )
        self.assertEqual(excel_bytes[:2], b"PK")

    def test_text_filter_removes_emoji_and_short_reviews(self) -> None:
        """Verifies emoji and short reviews are removed from the dataset."""
        from utils.text_filters import (
            contains_emoji,
            count_words,
            filter_reviews_dataframe,
            is_valid_review_text,
        )

        self.assertTrue(contains_emoji("Great app 😀"))
        self.assertFalse(contains_emoji("Great app experience"))
        self.assertEqual(count_words("one two three"), 3)
        self.assertFalse(is_valid_review_text("Nice app 😀"))
        self.assertFalse(is_valid_review_text("too short"))
        self.assertTrue(is_valid_review_text("This is a solid music app"))

        df = pd.DataFrame(
            {
                "review_text": [
                    "Love the playlists here",
                    "Good 👍",
                    "ok fine",
                    "Algorithm repeats same songs daily",
                ]
            }
        )
        filtered, stats = filter_reviews_dataframe(df)
        self.assertEqual(stats["removed_emoji"], 1)
        self.assertEqual(stats["removed_short"], 1)
        self.assertEqual(len(filtered), 2)

    def test_clear_data_cache(self) -> None:
        """Verifies local scraped and analyzed CSV cache files are removed."""
        from utils.session_reset import clear_data_cache

        with tempfile.TemporaryDirectory() as tmp:
            scraped_path = os.path.join(tmp, settings.SCRAPED_DATA_FILE)
            analyzed_path = os.path.join(tmp, settings.ANALYZED_DATA_FILE)
            with open(scraped_path, "w", encoding="utf-8") as handle:
                handle.write("review_text\nsample\n")
            with open(analyzed_path, "w", encoding="utf-8") as handle:
                handle.write("review_text\nsample\n")

            with patch.object(settings, "DATA_DIR", tmp):
                clear_data_cache()

            self.assertFalse(os.path.exists(scraped_path))
            self.assertFalse(os.path.exists(analyzed_path))

    def test_user_segment_profiles(self) -> None:
        """Verifies user segments are named and ranked from negative themed reviews."""
        from analysis.user_segments import UserSegmentAnalyzer
        from analysis.theme_classifier import ThemeClassifier

        raw = pd.DataFrame(
            {
                "source": ["Google Play Store", "Reddit"],
                "review_text": [
                    "Same songs repeat every day discover weekly is boring",
                    "The algorithm keeps playing the same artists over and over",
                ],
                "rating": [1, None],
                "sentiment_compound": [-0.6, -0.5],
                "sentiment_label": ["Negative", "Negative"],
            }
        )
        themed = ThemeClassifier().analyze(raw)
        analyzer = UserSegmentAnalyzer()
        profiles = analyzer.build_profiles(themed)
        self.assertEqual(len(profiles), 4)
        self.assertTrue(any(p["name"] == "Low-rating app store users" for p in profiles))
        pain = analyzer.pain_theme_summary(themed, top_n=3)
        self.assertTrue(len(pain) >= 1)

    def test_strategic_insights_shape(self) -> None:
        """Verifies strategic answers include problem statements and segment breakdown."""
        from analysis.insights_engine import InsightsEngine

        engine = InsightsEngine()
        raw = pd.DataFrame(
            {
                "source": ["Google Play Store"],
                "review_text": [
                    "The algorithm keeps recommending the same songs and nothing new ever shows up"
                ],
                "rating": [2],
            }
        )
        analyzed = engine.run_full_analysis(raw)
        answers = engine.answer_strategic_questions(analyzed, use_llm=False)
        self.assertGreater(len(answers), 0)
        first = answers[0]
        self.assertIn("problem_statement", first)
        self.assertIn("segment_breakdown", first)
        self.assertIn("llm_answer", first)
        self.assertNotIn("recommendations", first)

    def test_llm_analyzer_fallback_without_key(self) -> None:
        """Verifies insights work when no API key is configured."""
        from analysis.llm_analyzer import LLMAnalyzer
        from unittest.mock import patch

        sample = {
            "question": "Why do users struggle to discover new music?",
            "problem_statement": "Users feel stuck.",
            "summary": "Rule-based summary.",
            "key_stats": {"total_relevant_reviews": 2, "pct_of_total": 10, "pct_of_negative": 20},
            "quotes": [],
            "themes_data": {},
            "segment_breakdown": [],
        }
        with patch.object(LLMAnalyzer, "_resolve_api_key", return_value=None):
            analyzer = LLMAnalyzer()
            self.assertFalse(analyzer.is_available())
            enriched = analyzer.enrich_insights([sample])
            self.assertEqual(enriched[0]["llm_answer"], "Rule-based summary.")
            self.assertFalse(enriched[0]["llm_used"])

    def test_validation_quotes_negative_only(self) -> None:
        """Verifies validation quotes prefer negative themed reviews."""
        from utils.dashboard_context import validation_quotes

        df = pd.DataFrame(
            {
                "review_text": ["Love this app", "Same songs repeat every day on discover weekly"],
                "sentiment_label": ["Positive", "Negative"],
                "sentiment_compound": [0.8, -0.7],
                "source": ["Google Play Store", "Reddit"],
                "theme_Discovery Frustrations": [False, True],
                "primary_user_segment": ["General feedback", "Discovery & recommendation frustrated"],
            }
        )
        quotes = validation_quotes(df, n=3)
        self.assertEqual(len(quotes), 1)
        self.assertIn("repeat", quotes[0]["text"].lower())


if __name__ == "__main__":
    unittest.main()
