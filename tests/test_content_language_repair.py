import unittest
from types import SimpleNamespace

from scripts.backfill_content_languages import (
    PERSONALITY_FIELDS, READING_FIELDS, apply_missing, column, mark_actual_languages, missing,
)


class RepairRegressionTests(unittest.TestCase):
    def test_pre_malay_ready_row_is_still_selected(self):
        row = SimpleNamespace(generation_status="READY", languages_ready=["en", "zh"])
        for language in ("en", "zh"):
            for field in READING_FIELDS:
                setattr(row, column("readings", field, language), "existing")
        self.assertEqual(len(missing(row, "readings", "ms")), 4)
        mark_actual_languages(row, "readings")
        self.assertEqual(row.generation_status, "PARTIAL")

    def test_concurrent_existing_text_and_scores_are_preserved(self):
        row = SimpleNamespace(title_ms="Live task completed", overview_ms=None, ocean_score=20)
        apply_missing(row, {"title_ms": "Repair proposal", "overview_ms": "New Malay overview"})
        self.assertEqual(row.title_ms, "Live task completed")
        self.assertEqual(row.overview_ms, "New Malay overview")
        self.assertEqual(row.ocean_score, 20)

    def test_personality_ready_uses_fields_in_all_three_languages(self):
        row = SimpleNamespace(languages_ready=None)
        for language in ("en", "zh", "ms"):
            for field in PERSONALITY_FIELDS:
                setattr(row, column("personalities", field, language), "content")
        mark_actual_languages(row, "personalities")
        self.assertEqual(row.languages_ready, ["en", "zh", "ms"])
        self.assertEqual(row.generation_status, "READY")
        self.assertEqual(missing(row, "personalities", "ms"), [])


if __name__ == "__main__":
    unittest.main()
