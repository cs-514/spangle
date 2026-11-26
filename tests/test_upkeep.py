"""Upkeep jobs (upkeep/): schedule guard, QOTD rotation, amplifier merge, rewrite gates. No network."""
import json, os, unittest
from datetime import datetime, timezone, timedelta
from _helpers import ROOT
from upkeep import slot, qotd, amplifiers, rewrite
from upkeep.common import ET


class Slot(unittest.TestCase):
    def test_window_and_stamp(self):
        at = lambda h: datetime(2026, 11, 26, h, 5, tzinfo=ET)
        self.assertFalse(slot.due("am", 7, 3, at(6), {})[0])        # EST: the 11:00 UTC run lands at 6 AM ET
        self.assertTrue(slot.due("am", 7, 3, at(7), {})[0])
        self.assertTrue(slot.due("am", 7, 3, at(9), {})[0])         # GitHub started it late
        self.assertFalse(slot.due("am", 7, 3, at(10), {})[0])
        self.assertFalse(slot.due("am", 7, 3, at(8), {"am": "2026-11-26"})[0])  # already ran today


class Qotd(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "qotd_bank.json")) as f:
            self.bank = json.load(f)

    def test_never_same_author_or_reused_id(self):
        used = {"used_ids": [], "last_author": None, "history": []}
        day = datetime(2027, 1, 1)
        prev = None
        for i in range(40):
            today = (day + timedelta(i)).strftime("%Y-%m-%d")
            q = qotd.deterministic_pick(self.bank, used, today)
            self.assertNotEqual(q["author"], prev, today)
            self.assertNotIn(q["id"], used["used_ids"])
            self.assertTrue(q.get("verified") and q.get("source_type") in ("primary", "column"))
            qotd.record_use(used, q, today)
            prev = q["author"]

    def test_deweighted_author_picked_less(self):
        low = [p for p, w in (self.bank.get("author_weights") or {}).items() if float(w) < 1]
        self.assertTrue(low)
        used = {"used_ids": [], "history": [], "last_author": None}
        picks = [qotd.prefix(qotd.deterministic_pick(self.bank, used, f"2027-{m:02d}-{d:02d}"))
                 for m in range(1, 13) for d in range(1, 29)]
        share = picks.count(low[0]) / len(picks)
        self.assertLess(share, 1.0 / len({qotd.prefix(q) for q in self.bank["quotes"]}))

    def test_public_entry_has_no_headline(self):
        q = dict(self.bank["quotes"][0], headline="Legacy")
        e = qotd.public_entry(q, "2027-01-01")
        self.assertNotIn("headline", e)
        self.assertEqual(e["quote"], qotd.dashes(q["quote"]))

    def test_shortlist_excludes_yesterdays_author(self):
        used = {"used_ids": [], "history": [{"date": "2027-01-01", "bank_id": "x", "author": "C. S. Lewis"}]}
        self.assertTrue(all(q["author"] != "C. S. Lewis" for q in qotd.shortlist(self.bank, used, "2027-01-02")))


class Amplifiers(unittest.TestCase):
    NOW = datetime(2026, 11, 26, 12, tzinfo=timezone.utc)
    SRC = {"max_age_hours": 48, "feeds": [{"id": "a", "kind": "mastodon", "api": "https://h.example/api/v1",
                                            "accounts": {"acct1": 1.0, "acct2": 1.0}, "consensus": True},
                                           {"id": "b", "kind": "x", "accounts": {"acct3": 0.7}}]}

    def test_blocked_feed_keeps_previous_items_and_tags(self):
        prev = {"items": [{"url": "https://n.example/old", "text": "old", "ts": "2026-11-26T01:00:00Z", "weight": 1.0},
                          {"url": "https://n.example/expired", "text": "x", "ts": "2026-11-20T01:00:00Z", "weight": 1.0}]}
        fetchers = {"mastodon": lambda *a: ([], 0, 2), "x": lambda *a: None}
        p, report = amplifiers.build_payload(self.SRC, prev, self.NOW, fetchers)
        self.assertEqual([it["url"] for it in p["items"]], ["https://n.example/old"])
        self.assertEqual(p["sources_blocked"], 1)
        self.assertFalse(any("acct" in line for line in report))

    def test_fresh_items_never_carry_account_names(self):
        def masto(feed, now, max_age, skip_hosts):
            mk = lambda a: {"url": "https://n.example/s", "text": "story", "ts": "2026-11-26T11:00:00Z", "weight": 1.0,
                            "_acct": a, "_w": 1.0}
            return [mk("acct1"), mk("acct2")], 2, 0
        p, _ = amplifiers.build_payload(self.SRC, {}, self.NOW, {"mastodon": masto, "x": lambda *a: None})
        blob = json.dumps(p)
        self.assertNotIn("acct1", blob); self.assertNotIn("acct2", blob)
        self.assertEqual(p["items"][0]["consensus_accounts"], 2)
        self.assertEqual(p["items"][0]["feed"], "a")
        self.assertIn("a", p["fetched"])


class RewriteGates(unittest.TestCase):
    def test_gates(self):
        q = {"https://n.example/1", "https://n.example/2", "https://n.example/3"}
        done = {"https://n.example/1": "Senate Passes Border Bill -- Dems Fume",
                "https://n.example/2": "The Big Week",                    # fragment
                "https://n.example/3": "",                                # skipped
                "https://other.example/": "Not In Queue Passes Bill"}
        ok, rej = rewrite.gate(done, q, {})
        self.assertEqual(ok, {"https://n.example/1": "Senate Passes Border Bill—Dems Fume"})
        self.assertEqual(rej, {"fragment": 1})


if __name__ == "__main__":
    unittest.main()
