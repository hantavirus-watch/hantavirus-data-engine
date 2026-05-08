import unittest
from types import SimpleNamespace

from fetch_data import (
    clean_location_candidate,
    extract_location_candidates,
    is_google_news_relevant,
    keyword_filtered_entries,
)


class FetchDataTests(unittest.TestCase):
    def test_google_news_relevant_accepts_concrete_event_title(self):
        entry = {
            "title": "Three passengers evacuated from hantavirus-hit cruise ship as new case is confirmed in Switzerland - NBC News"
        }

        self.assertTrue(is_google_news_relevant(entry))

    def test_google_news_relevant_rejects_explainer_title(self):
        entry = {
            "title": "What the numbers tell us about hantavirus - CNN"
        }

        self.assertFalse(is_google_news_relevant(entry))

    def test_clean_location_candidate_rejects_non_location_fragments(self):
        self.assertIsNone(clean_location_candidate("Live Updates"))

    def test_extract_location_candidates_preserves_specific_places(self):
        candidates = extract_location_candidates(
            "Spain readies for evacuations as a hantavirus-hit cruise ship heads for Canary Islands - NPR"
        )

        self.assertIn("Spain", candidates)
        self.assertIn("Canary Islands", candidates)

    def test_keyword_filtered_entries_keeps_only_matching_rss_items(self):
        feed = SimpleNamespace(
            entries=[
                {"title": "Regional health bulletin", "summary": "General respiratory updates"},
                {"title": "PAHO advisory", "summary": "Recent hantavirus cases under investigation"},
            ]
        )

        filtered_entries = keyword_filtered_entries(feed)

        self.assertEqual(len(filtered_entries), 1)
        self.assertEqual(filtered_entries[0]["title"], "PAHO advisory")


if __name__ == "__main__":
    unittest.main()