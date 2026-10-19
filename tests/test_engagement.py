"""Engagement + consensus signals (fictional data only; the real feeds/terms live in private secrets)."""
import json, os, unittest
from datetime import datetime, timezone, timedelta
from _helpers import story, ROOT
from ranking import engagement, consensus
import ranking

NOWS = datetime.now(timezone.utc)


def cl(i, *items, **flags):
    c = {"id": i, "items": list(items), "signals": {"alignment": 0.7, "faction": 0.5}}
    c.update(flags)
    return c


def data(urls=(), terms=(), age_h=0.5):
    return json.dumps({"generated_at": (NOWS - timedelta(hours=age_h)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                       "urls": list(urls), "terms": list(terms)})


S = {"lean_filter": {}}


class Env:
    def __init__(self, **kv):
        self.kv = kv

    def __enter__(self):
        self.old = {k: os.environ.get(k) for k in self.kv}
        os.environ.update(self.kv)

    def __exit__(self, *a):
        for k, v in self.old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class Engagement(unittest.TestCase):
    def setUp(self):
        self._lean = engagement.lean._CFG
        engagement.lean._CFG = {}   # generic lean config for tests

    def tearDown(self):
        engagement.lean._CFG = self._lean

    def run_sig(self, clusters, payload, cfg=None):
        with Env(ENGAGEMENT_DATA=payload):
            return engagement.compute(clusters, S, {"alignment_cfg": {"engagement": cfg or {}}})

    def test_url_match_whole_cluster(self):
        a = story("Border Wall Vote Passes House", link="https://www.example-right.com/politics/border-wall-vote.amp")
        b = story("House Passes Border Wall Funding", link="https://other.com/2026/10/16/house-border-wall/")
        out = self.run_sig([cl(1, a, b), cl(2, story("Unrelated Weather Story"))],
                           data([{"url": "https://example-right.com/politics/border-wall-vote", "score": 0.9}]))
        self.assertAlmostEqual(out[1], 0.9)
        self.assertEqual(out[2], 0.0)

    def test_sibling_by_slug(self):
        a = story("Trump Signs Executive Order Putting New Sanctions on Russia", link="https://a.com/x1")
        out = self.run_sig([cl(1, a)], data([{"url": "https://b.com/government/trump-signs-executive-order-putting-new-sanctions-russia", "score": 0.8}]))
        self.assertAlmostEqual(out[1], 0.64)

    def test_fuzzy_rejects_opposing_actions(self):
        """A waiver story is not the same story as an order imposing new sanctions, despite shared words."""
        a = story("President Waives Russia Sanctions Ordered by Law Named for Senator", link="https://a.com/waiver")
        u = [{"url": "https://b.com/gov/president-signs-order-putting-new-russia-sanctions-law-named-senator", "score": 1.0}]
        self.assertEqual(self.run_sig([cl(1, a)], data(u))[1], 0.0)

    def test_fuzzy_needs_same_story(self):
        a = story("Senate Border Funding Vote Delayed Again", link="https://a.com/x")
        u = [{"url": "https://b.com/news/governor-border-funding-vote-county-fair-results", "score": 1.0}]
        self.assertEqual(self.run_sig([cl(1, a)], data(u))[1], 0.0)

    def test_owner_cluster_gets_boost_not_lookalike(self):
        own = story("President Signs Order Putting New Sanctions on Russia", link="https://b.com/gov/president-signs-order-new-sanctions-russia")
        look = story("President Signs New Russia Sanctions Order", link="https://a.com/other")
        u = [{"url": "https://b.com/gov/president-signs-order-new-sanctions-russia", "score": 1.0}]
        cs = [cl(1, look), cl(2, own)]
        out = self.run_sig(cs, data(u))
        self.assertAlmostEqual(out[2], 1.0)
        self.assertEqual(out[1], 0.0)
        self.assertEqual(cs[1]["engagement_exact"], 1.0)

    def test_fuzzy_only_is_not_lead_credit(self):
        a = story("Trump Signs Executive Order Putting New Sanctions on Russia", link="https://a.com/x1")
        cs = [cl(1, a)]
        out = self.run_sig(cs, data([{"url": "https://b.com/government/trump-signs-executive-order-putting-new-sanctions-russia", "score": 0.8}]))
        self.assertGreater(out[1], 0.5)
        self.assertEqual(cs[0]["engagement_exact"], 0.0)

    def test_retreat_flagged_not_boosted(self):
        c = cl(1, story("Hot Story Here Today", link="https://e.com/hot-story-here"))
        c["signals"]["retreat"] = 0.3
        self.assertEqual(self.run_sig([c], data([{"url": "https://e.com/hot-story-here", "score": 1.0}]))[1], 0.0)

    def test_lead_ignores_fuzzy_engagement(self):
        from ranking import lead
        import inspect
        src = inspect.getsource(lead)
        self.assertIn('c.get("engagement_exact"', src)
        self.assertNotIn('sg.get("engagement"', src)
        self.assertIn("score_lead", src)

    def test_opposed_helper(self):
        from ranking.story_match import opposed
        self.assertTrue(opposed("Mayor Lifts Curfew", "Mayor Imposes New Curfew"))
        self.assertTrue(opposed("Tariffs Paused", "Tariffs Expanded to Steel"))
        self.assertFalse(opposed("Senate Passes Wall Funding", "Wall Funding Clears Senate"))
        self.assertFalse(opposed("Agency Drops Rule", "Agency Drops Rule After Outcry"))

    def test_terms_smaller(self):
        a = story("Rubio Declares America First Foreign Policy at State Department")
        out = self.run_sig([cl(1, a)], data(terms=[{"term": "State Department Declares America First Foreign Policy Under Rubio", "score": 1.0}]))
        self.assertAlmostEqual(out[1], 0.35)
        self.assertLess(out[1], 0.5)

    def test_no_boost_when_not_eligible(self):
        u = [{"url": "https://e.com/hot-story-here", "score": 1.0}]
        mk = lambda **f: cl(1, story("Hot Story Here Today", link="https://e.com/hot-story-here"), **f)
        self.assertEqual(self.run_sig([mk(excluded=True)], data(u))[1], 0.0)          # defeatist
        c = mk(); c["signals"]["faction"] = 0.05                                        # in-party favorable
        self.assertEqual(self.run_sig([c], data(u))[1], 0.0)
        c = mk(); c["signals"]["alignment"] = 0.3                                       # misaligned
        self.assertEqual(self.run_sig([c], data(u))[1], 0.0)
        self.assertEqual(self.run_sig([mk(celebrity=True)], data(u))[1], 0.0)
        engagement.lean._CFG = {"left_terms": ["hot story"]}                           # left-leaning framing
        self.assertEqual(self.run_sig([mk()], data(u))[1], 0.0)

    def test_stale_or_missing(self):
        import contextlib, io
        c = [cl(1, story("X"))]
        buf = io.StringIO()  # keep the fixture's stale warning out of the CI log (it is not the real data)
        with contextlib.redirect_stdout(buf):
            self.assertIsNone(self.run_sig(c, data(age_h=9)))
            self.assertIsNone(self.run_sig(c, ""))
            self.assertIsNone(self.run_sig(c, "{bad json"))
        self.assertIn("stale", buf.getvalue())

    def test_canon(self):
        self.assertEqual(engagement.ucanon("https://www.foxnews.com/politics/a-b.amp"), "foxnews.com/politics/a-b")
        self.assertEqual(engagement.ucanon("https://m.nypost.com/2026/10/16/x/amp/"), "nypost.com/2026/10/16/x")

    def test_rank_lifts_engaged_story(self):
        """With the signal weighted, an engaged aligned story outranks an otherwise-equal one."""
        a = story("Senate Passes Border Wall Funding Bill", link="https://e.com/a-hot")
        b = story("Senate Debates Farm Subsidy Measure", link="https://e.com/b-cold")
        cs = [cl(1, a), cl(2, b)]
        res = {"engagement": {1: 1.0, 2: 0.0}, "recency": {1: 0.5, 2: 0.5}}
        ranking._combine(cs, res, {"engagement": 0.6, "recency": 1.0})
        self.assertGreater(cs[0]["score"], cs[1]["score"])


class Consensus(unittest.TestCase):
    def test_reads_consensus_items(self):
        items = [{"url": "https://www.e.com/big-story", "text": "Big story", "consensus": 0.8, "consensus_accounts": 3},
                 {"url": "https://e.com/solo", "text": "solo", "weight": 1.0}]
        with Env(AMPLIFIER_ITEMS=json.dumps(items)):
            out = consensus.compute([cl(1, story("Big Story Breaks", link="https://e.com/big-story/")), cl(2, story("Solo", link="https://e.com/solo"))], S, {})
        self.assertAlmostEqual(out[1], 0.8)
        self.assertEqual(out[2], 0.0)   # single-account items carry no consensus

    def test_none_without_consensus(self):
        with Env(AMPLIFIER_ITEMS=json.dumps([{"url": "https://e.com/a", "text": "a"}])):
            self.assertIsNone(consensus.compute([cl(1, story("A"))], S, {}))


class Wiring(unittest.TestCase):
    def test_post_signals_registered_and_x_stub_gone(self):
        self.assertEqual([m.NAME for m in ranking.POST], ["engagement", "consensus"])
        self.assertNotIn("x", [m.NAME for m in ranking.SOCIAL])
        s = json.load(open(f"{ROOT}/settings.json"))
        self.assertEqual(s["weights"]["engagement"], 0.0)   # real weights are private
        self.assertNotIn("x", s["social"])

    def test_workflow_passes_secret(self):
        self.assertIn("ENGAGEMENT_DATA: ${{ secrets.ENGAGEMENT_DATA }}", open(f"{ROOT}/.github/workflows/build.yml").read())


class AmplifierFreshness(unittest.TestCase):
    def _stale(self, payload):
        import contextlib, io
        from ranking import amplifiers
        buf = io.StringIO()
        with Env(AMPLIFIER_ITEMS=json.dumps(payload)), contextlib.redirect_stdout(buf):
            return amplifiers.staleness(6), buf.getvalue()

    def ts(self, h):
        return (NOWS - timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def test_fresh_harvest_with_blocked_source_is_not_stale(self):
        st, out = self._stale({"generated_at": self.ts(0.2), "sources_blocked": 1,
                               "items": [{"url": "https://e.com/a", "text": "a", "ts": self.ts(40)}]})
        self.assertFalse(st)
        self.assertIn("1 source(s) blocked", out)

    def test_old_harvest_is_stale(self):
        st, _ = self._stale({"generated_at": self.ts(9), "items": []})
        self.assertTrue(st)

    def test_legacy_list_uses_newest_item(self):
        self.assertTrue(self._stale([{"url": "https://e.com/a", "text": "a", "ts": self.ts(47)}])[0])
        self.assertFalse(self._stale([{"url": "https://e.com/a", "text": "a", "ts": self.ts(1)}])[0])

    def test_items_age_out_individually_in_dict_payload(self):
        from ranking import amplifiers
        p = {"generated_at": self.ts(0.1), "items": [{"url": "https://e.com/old", "text": "old story", "ts": self.ts(60)},
                                                   {"url": "https://e.com/new", "text": "new story", "ts": self.ts(1)}]}
        with Env(AMPLIFIER_ITEMS=json.dumps(p)):
            got = amplifiers._items_from_env(48)
        self.assertEqual(len(got), 1)

    def test_consensus_reads_dict_and_ages_out(self):
        a = story("Senate Passes Border Wall Funding Bill", link="https://e.com/a")
        p = {"generated_at": self.ts(0.1), "items": [
            {"url": "https://e.com/a", "text": "x", "ts": self.ts(1), "consensus": 0.8},
            {"url": "https://e.com/b", "text": "y", "ts": self.ts(60), "consensus": 1.0}]}
        b = story("Something Else Entirely Happens Today", link="https://e.com/b")
        with Env(AMPLIFIER_ITEMS=json.dumps(p)):
            out = consensus.compute([cl(1, a), cl(2, b)], S, {})
        self.assertAlmostEqual(out[1], 0.8)
        self.assertEqual(out[2], 0.0)
