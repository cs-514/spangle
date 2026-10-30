"""Quote of the Day box: a plain 'Quote of the Day' heading, then the quote text, then the attribution line.
No per-quote headline is rendered or required; legacy "headline" fields in the bank are ignored."""
import json, unittest
from _helpers import ROOT
import aggregator as A


class PlainHeading(unittest.TestCase):
    def test_today_renders_plain_heading(self):
        today = json.load(open(f"{ROOT}/quote_of_the_day.json"))
        s = A.quote_as_story(today)
        self.assertEqual(s["display"], "Quote of the Day")
        self.assertEqual(s["quote_text"], today["quote"])

    def test_fallback_ignores_headline(self):
        for d in range(1, 29):
            q = A.fallback_quote(f"2026-03-{d:02d}")
            self.assertTrue(q and q["quote"])
            self.assertEqual(A.quote_as_story(q)["display"], "Quote of the Day")

    def test_sowell_rotation_cut(self):
        bank = json.load(open(f"{ROOT}/qotd_bank.json"))
        self.assertLessEqual(bank["author_weights"]["ts"], 0.4)

    def test_retired_never_picked(self):
        seen = set()
        for d in range(1500):
            seen.add(A.fallback_quote(f"2026-{(d // 28) % 12 + 1:02d}-{(d % 28) + 1:02d}")["id"])
        retired = {q["id"] for q in json.load(open(f"{ROOT}/qotd_bank.json"))["quotes"]
                   if q.get("status") in ("retired", "low_impact")}
        self.assertFalse(seen & retired)
