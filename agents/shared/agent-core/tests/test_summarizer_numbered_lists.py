import importlib.util
from pathlib import Path
import unittest


_MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "agent_core"
    / "skills"
    / "summarizer.py"
)
_SPEC = importlib.util.spec_from_file_location("summarizer_under_test", _MODULE_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"Cannot load summarizer from {_MODULE_PATH}")
_SUMMARIZER = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_SUMMARIZER)
summarize_key_points = _SUMMARIZER.summarize_key_points


class SummarizerNumberedListsTests(unittest.TestCase):
    def test_meaningful_bullet_wins_over_decimal(self):
        text = "3.141592653589793\n- Preserve the meaningful bullet point."
        self.assertEqual(
            summarize_key_points(text, max_points=1),
            ["Preserve the meaningful bullet point."],
        )

    def test_valid_numbered_items_are_cleaned(self):
        for marker in ("1. ", "12. ", "2.\t"):
            with self.subTest(marker=marker):
                self.assertEqual(
                    summarize_key_points(
                        marker + "Preserve the meaningful numbered item.",
                        max_points=1,
                    ),
                    ["Preserve the meaningful numbered item."],
                )

    def test_zero_max_points_returns_empty(self):
        text = (
            "3.141592653589793\n"
            "1. Preserve the meaningful numbered item.\n"
            "- Preserve the meaningful bullet point.\n"
            "This paragraph is long enough for sentence extraction."
        )
        self.assertEqual(summarize_key_points(text, max_points=0), [])


if __name__ == "__main__":
    unittest.main()
