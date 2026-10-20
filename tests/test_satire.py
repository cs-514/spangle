import unittest
from _helpers import NOW, story
import aggregator as A
from ranking import satire
from test_age_limits import settings, clusters

QA = dict(source="Washington Free Beacon", link="https://freebeacon.com/satire/exclusive-qa-breaking-the-ice-with-a-candidate/",
          cats="Satire 2026 elections Michigan Parody Senate", tags=["Satire", "2026 elections", "Michigan", "Parody", "Senate"])


class Detect(unittest.TestCase):
    def sig(self, title="Headline", **kw):
        return satire.signal(story(title, **kw))

    def test_outlet_and_domain(self):
        self.assertEqual(self.sig(source="The Babylon Bee"), "outlet")
        self.assertEqual(self.sig(source="Bongino Report", link="https://babylonbee.com/news/man-does-thing"), "outlet")
        self.assertEqual(self.sig(source="x", link="https://www.theonion.com/a-b-c-123"), "outlet")

    def test_per_item_section_of_real_outlet(self):
        self.assertEqual(self.sig("Exclusive Q&A: Breaking the Ice With a Candidate", **QA), "url")
        self.assertEqual(self.sig(source="Washington Free Beacon", link="https://freebeacon.com/x/y/", tags=["Parody"]), "category")
        self.assertEqual(self.sig(source="Some Feed", link="https://ex.com/a", cats="Satire"), "category")
        self.assertEqual(self.sig("Satire: Congress Votes to Abolish Mondays"), "title")
        self.assertEqual(self.sig("Congress Votes to Abolish Mondays (Parody)"), "title")
        self.assertEqual(self.sig(desc="This is satire. Nothing here happened."), "summary")

    def test_real_journalism_not_satire(self):
        for kw in [dict(source="Washington Free Beacon", link="https://freebeacon.com/culture/laughing-in-a-hard-loud-world/",
                        tags=["Culture", "Book reviews"], desc="A new book on the uses of satire and comedy in politics."),
                   dict(source="The Free Press", link="https://www.thefp.com/p/an-interview"),
                   dict(source="Not the Bee", link="https://notthebee.com/article/bbc-says-riots-are-mostly-peaceful/"),
                   dict(source="Fox News", link="https://www.foxnews.com/entertainment/snl-parody-of-debate", cats="Entertainment")]:
            self.assertIsNone(self.sig("Satirist Says Comedy Is Hard", **kw), kw)


class Placement(unittest.TestCase):
    def test_never_lead_or_top_but_columns_ok(self):
        items = [story("Exclusive Q&A: Breaking the Ice With a Candidate", 1, **QA),
                 story("Bee Story", 1, source="The Babylon Bee", link="https://babylonbee.com/news/bee-story"),
                 story("Real 1", 2), story("Real 2", 3), story("Real 3", 4), story("Real 4", 5)]
        lead, top, cols = A.place(clusters(items), settings(), {"now": NOW})
        front = [lead["title"]] + [x["title"] for x in top]
        self.assertEqual(front, ["Real 1", "Real 2", "Real 3"])
        flat = [x["title"] for c in cols for x in c]
        self.assertIn("Exclusive Q&A: Breaking the Ice With a Candidate", flat)
        self.assertIn("Bee Story", flat)

    def test_not_the_bee_front_eligible(self):
        s = settings()
        self.assertTrue(A.fits(story("BBC Says Riots Are Mostly Peaceful", 1, source="Not the Bee",
                                     link="https://notthebee.com/article/bbc"), "top", s, NOW))

    def test_fallback_lead_skips_satire(self):
        items = [story("Bee Story", 30, source="The Babylon Bee", link="https://babylonbee.com/news/b"), story("Old real", 31)]
        lead, top, cols = A.place(clusters(items), settings(), {"now": NOW})
        self.assertEqual(lead["title"], "Old real")


if __name__ == "__main__":
    unittest.main()
