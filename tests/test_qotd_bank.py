import json, unittest
from _helpers import ROOT
import aggregator as A


class Bank(unittest.TestCase):
    def setUp(self):
        self.bank = json.load(open(f"{ROOT}/qotd_bank.json"))["quotes"]

    def test_ids_unique(self):
        ids = [q["id"] for q in self.bank]
        self.assertEqual(len(ids), len(set(ids)))

    def test_schema(self):
        for q in self.bank:
            for k in ("id", "quote", "author", "work", "verification_url", "verified", "source_type"):
                self.assertIn(k, q, q["id"])
            self.assertTrue(q["verification_url"].startswith("https://"), q["id"])
            self.assertLessEqual(len(q["quote"].split()), A.quote_word_limit(q), q["id"])
            if q.get("headline"):
                self.assertNotIn("'", q["headline"] + q["quote"], q["id"])  # curly quotes only
                self.assertNotIn('"', q["headline"] + q["quote"], q["id"])

    def test_guests_are_weighted(self):
        guests = [q for q in self.bank if q["id"].startswith("guest-")]
        self.assertTrue(guests)
        for q in guests:
            self.assertTrue(q.get("guest"))
            self.assertLess(q["weight"], 1)

    def test_weighted_pick(self):
        items = [{"id": "a"}, {"id": "g", "weight": 0.25}]
        picks = [A.weighted_pick(items, h)["id"] for h in range(0, 125000, 7)]
        share = picks.count("g") / len(picks)
        self.assertAlmostEqual(share, 0.2, delta=0.02)

    def test_guests_rare_in_fallback(self):
        import collections, datetime
        c = collections.Counter()
        for d in range(1200):
            day = (datetime.date(2026, 1, 1) + datetime.timedelta(d)).isoformat()
            c[A.fallback_quote(day)["id"].startswith("guest-")] += 1
        self.assertLess(c[True] / 1200, 0.02)

    def test_long_public_domain_payoff_eligible(self):
        q = next(q for q in self.bank if q["id"] == "guest-pyle-001")
        self.assertGreater(len(q["quote"].split()), 60)
        self.assertTrue(q["quote"].endswith("faithful in love."))


class CuratedHeadline(unittest.TestCase):
    def test_bank_headline_kept_verbatim(self):
        import os, tempfile
        with tempfile.TemporaryDirectory() as d:
            json.dump({"quotes": [{"id": "hom-x", "quote": "One omen is best, to fight for our own country.", "author": "Homer",
                                   "work": "Iliad", "headline": "One Omen Is Best", "verification_url": "https://example.org",
                                   "verified": True, "source_type": "primary"}]}, open(os.path.join(d, "b.json"), "w"))
            old, A.HERE = A.HERE, d
            try:
                q = A.fallback_quote("2026-10-17", "b.json")
            finally:
                A.HERE = old
        self.assertEqual(q["headline"], "One Omen Is Best")

    def test_homer_entries(self):
        bank = json.load(open(f"{ROOT}/qotd_bank.json"))["quotes"]
        hom = [q for q in bank if q["id"].startswith("hom-")]
        self.assertEqual([q["id"] for q in hom], [f"hom-{i:03d}" for i in range(1, 16)])
        for q in hom:
            self.assertTrue(q["public_domain"])
            self.assertNotIn("weight", q)
            self.assertTrue(q["verification_url"].startswith("https://www.gutenberg.org/ebooks/"))
