import json, os, tempfile, unittest
from _helpers import ROOT, NOW, story
import aggregator as A
from ranking import headline


class QuotePlacement(unittest.TestCase):
    def test_slot(self):
        cols = [[story(f"c{c}-{i}") for i in range(10)] for c in range(3)]
        s = {"placement": {"quote_of_the_day": {"enabled": True, "column": 1, "index": 7}}}
        out = A.inject_quote(cols, s)
        self.assertTrue(out[1][7].get("quote_item"))
        self.assertEqual(sum(1 for c in out for x in c if x.get("quote_item")), 1)

    def test_stale_file_falls_back_to_bank(self):
        d = tempfile.mkdtemp()
        json.dump({"date": "2000-01-01", "quote": "Stale.", "author": "X", "headline": "Stale"}, open(f"{d}/q.json", "w"))
        old, A.HERE = A.HERE, d
        try:
            json.dump({"quotes": [{"id": "p1", "quote": "Fresh primary quote here.", "author": "Y", "work": "W",
                                   "verification_url": "https://example.org", "verified": True, "source_type": "primary"},
                                  {"id": "s1", "quote": "Secondary.", "author": "Z", "verified": False, "source_type": "secondary"}]},
                      open(f"{d}/b.json", "w"))
            q = A.load_daily_quote("q.json", today="2026-10-15", bank_file="b.json")
        finally:
            A.HERE = old
        self.assertEqual(q["author"], "Y")
        self.assertEqual(q["date"], "2026-10-15")

    def test_repo_bank_is_primary_only(self):
        b = json.load(open(f"{ROOT}/qotd_bank.json"))["quotes"]
        self.assertTrue(b)
        for q in b:
            self.assertTrue(q["verified"])
            self.assertNotIn("wikiquote", q["verification_url"])
            self.assertNotIn("azquotes", q["verification_url"])


class Render(unittest.TestCase):
    def html(self):
        lead = story("Lead Story", 1, outlets_n=3)
        top = [story("Top Take", 2, opinion=True)]
        q = A.quote_as_story({"quote": "Q text.", "author": "George Washington", "work": "Farewell Address"})
        return A.render(lead, top, [[q], [], []], NOW, [], {"placement": {}})

    def test_meta(self):
        h = self.html()
        self.assertNotRegex(h, r"\+\d+ outlet")  # coverage counts are internal only
        self.assertNotIn("Opinion", h)  # Drudge-style: no opinion tag text anywhere on the page
        self.assertNotIn("OPINION", h)
        self.assertNotIn('<div class="meta"> · ', h)
        self.assertIn('<div class="kicker"><span class="tag">Quote</span></div>', h)
        # QUOTE kicker sits above the headline; source line stays below the quote text
        k, a, qt, src = (h.index('<div class="kicker"><span class="tag">Quote</span></div>'), h.index('>Q text.<') if '>Q text.<' in h else h.index('Q text.'),
                         h.index('<div class="qt">'), h.index('George Washington · Farewell Address'))
        self.assertTrue(k < a <= qt < src)
        self.assertNotIn('<span class="tag">Quote</span> · ', h)
        self.assertIn("All rights belong to their respective publishers. © 2026 Spangle", h)


class Shorten(unittest.TestCase):
    def test_trims(self):
        t = "A Trans Substitute Teacher Was Just Convicted for Threatening ‘Murder Spree’ at Virginia High School"
        s = headline.shorten(t)
        self.assertLessEqual(len(s), 70)
        self.assertTrue(s.startswith("Trans Substitute Teacher Convicted"))
        self.assertNotIn("…", s)

    def test_noop_when_short(self):
        self.assertEqual(headline.shorten("Senate Passes Bill"), "Senate Passes Bill")


class Outlets(unittest.TestCase):
    def test_no_raw_domains(self):
        items = [story("x", source="lifezette.com"), story("y", source="hollywoodintoto.com")]
        A.display_outlets(items)
        self.assertEqual([i["source"] for i in items], ["LifeZette", "Hollywood in Toto"])


if __name__ == "__main__":
    unittest.main()


class WpJson(unittest.TestCase):
    def test_parse_and_skip_paid(self):
        posts = [{"date_gmt": "2026-10-15T20:28:10", "link": "https://okeefemediagroup.com/a/",
                  "title": {"rendered": "O\u2019Keefe Files Motion"}, "categories": [213]},
                 {"date_gmt": "2026-10-14T20:00:00", "link": "https://okeefemediagroup.com/b/",
                  "title": {"rendered": "Paid Post"}, "categories": [210, 1]}]
        out = A.wp_json_items(posts, "O’Keefe Media Group", False, {"exclude_categories": [210]})
        self.assertEqual([x["title"] for x in out], ["O’Keefe Files Motion"])
        self.assertEqual(out[0]["when"].hour, 20)


class OpinionInternal(unittest.TestCase):
    def test_classify(self):
        from ranking import opinion as O
        self.assertTrue(O.classify(story("Will Bill and Hillary Clinton Please Just Go Away?", source="RedState",
                                         link="https://redstate.com/wardclark/2026/10/15/x")))
        self.assertTrue(O.classify(story("Is Rep. Omar a U.S. Citizen?", source="American Thinker",
                                         link="https://www.americanthinker.com/blog/2026/10/x/")))
        self.assertTrue(O.classify(story("Whitlock on Entitlement", source="The Blaze", link="https://www.theblaze.com/shows/x")))
        self.assertTrue(O.classify(story("Some Headline", cats="News Opinion")))
        self.assertFalse(O.classify(story("Pentagon Sends Hundreds of Troops South", source="Fox News",
                                          link="https://www.foxnews.com/politics/x")))
        self.assertFalse(O.classify(story("SCOTUS Hands the RNC Another Election Win", source="Townhall",
                                          link="https://townhall.com/news/amy-curtis/2026/10/15/x")))


class Truncated(unittest.TestCase):
    U = "https://www.breitbart.com/politics/2026/10/15/report-feds-seize-ilhan-omars-cellphone-in-immigration-fraud-investigatio/"
    T = "Feds Seize Ilhan Omar’s Cellphone in Immigration Fraud Investigatio"

    def test_detect_and_repair(self):
        v = headline.vocabulary([self.T, "Omar Investigation Widens", "FBI investigation into letters", "DOJ Investigation Expands", "Trump Signs the Bill"])
        self.assertTrue(headline.truncated(self.T, self.U, v))
        self.assertEqual(headline.repair_truncated(self.T, self.U, v), self.T[:-len("Investigatio")] + "Investigation")
        self.assertTrue(headline.truncated("Senate Votes on Immigra", "https://x.com/senate-votes-on-immigration-bill/"))
        self.assertTrue(headline.truncated("Senate Passes the Big Bill…"))
        self.assertFalse(headline.truncated("Trump Signs the Bill", "https://x.com/trump-signs-the-bill/", v))

    def test_override(self):
        self.assertEqual(headline.overrides()[self.U], "Feds Seize Omar’s Cellphone in Immigration Fraud Probe")

    def test_truncated_never_leads(self):
        import test_age_limits as T
        items = [story("Cut Off Headline Investigatio", 1, truncated=True), story("Whole Headline Here", 2)]
        lead, top, cols = A.place(T.clusters(items), T.settings(), {"now": NOW})
        self.assertEqual(lead["title"], "Whole Headline Here")


class OverrideAfterSwap(unittest.TestCase):
    def test_sibling_override_and_cut_sibling_avoided(self):
        u = Truncated.U
        lead = story("Ilhan Omar's husband snaps over rumors she fled US after federal immigration fraud raid", 1,
                     link="https://www.foxnews.com/politics/x")
        cut = story(Truncated.T, 1, link=u, source="Breitbart")
        l, t, c, st = A.decorate_headlines(lead, [], [[], [], []], [{"items": [lead, cut]}])
        self.assertNotIn("Investigatio", l["display"].split()[-1] + " ")  # never shows the cut-off form
