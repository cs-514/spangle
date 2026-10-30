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


class SourceLink(unittest.TestCase):
    def render(self, q):
        from _helpers import story, NOW
        return A.render(story("Lead Story", 1), [], [[A.quote_as_story(q)], [], []], NOW, [], {"placement": {}})

    def test_attribution_links_to_source(self):
        h = self.render({"quote": "Q text.", "author": "X", "work": "W", "verification_url": "https://example.org/src"})
        self.assertIn('<div class="meta"><a href="https://example.org/src" rel="noopener">X · W</a></div>', h)
        self.assertIn('<div class="qh">Quote of the Day</div>', h)  # heading stays plain, unlinked text
        self.assertNotIn('<a href="https://example.org/src" rel="noopener">Quote of the Day', h)

    def test_no_url_no_link(self):
        h = self.render({"quote": "Q text.", "author": "X", "work": "W"})
        self.assertIn('<div class="meta">X · W</div>', h)
        self.assertNotIn('href="#"', h[h.index('<li class="qotd">'):])

    def test_today_links_to_its_source(self):
        today = json.load(open(f"{ROOT}/quote_of_the_day.json"))
        if today.get("verification_url"):
            self.assertIn(f'<a href="{today["verification_url"]}" rel="noopener">', self.render(today))
