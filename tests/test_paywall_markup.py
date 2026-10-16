import unittest
from _helpers import story, NOW
import aggregator as A
from ranking import headline

BLAZE_PREMIUM = ('<meta name="sailthru.tags" content="god,faith,topic-opinion,topic-premium,topic-archive"/>'
                 "<script>window.__rmEngagementContext={page:{type:\"post\"},custom:{sections:['Opinion','Premium','Archive']}}</script>")
BLAZE_SECTIONS_ONLY = "<script>const pageparams={'post_sections':\"['Opinion', 'Premium', 'Archive']\"}</script>"
BLAZE_FREE = ('<meta name="sailthru.tags" content="new-jersey,crime,topic-news"/>'
              "<script>window.__rmEngagementContext={custom:{sections:['News','Politics']}}</script>"
              '<div class="bottom-paywall"></div><div class="unlock-article"></div>')  # empty mounts on every Blaze page


class BlazeMarkup(unittest.TestCase):
    def test_premium_detected(self):
        self.assertIsNotNone(A.wall_marker(BLAZE_PREMIUM))
        self.assertIsNotNone(A.wall_marker(BLAZE_SECTIONS_ONLY))
        self.assertIsNotNone(A.wall_marker('{"isAccessibleForFree": false}'))

    def test_free_blaze_page_not_flagged(self):
        self.assertIsNone(A.wall_marker(BLAZE_FREE))


class SiblingSwapRespectsWalls(unittest.TestCase):
    def setUp(self):
        A.WALL_CACHE.clear()
        self.orig = A._url_ok
        A._url_ok = lambda s: "theblaze.com" not in s["link"]

    def tearDown(self):
        A._url_ok = self.orig
        A.WALL_CACHE.clear()

    def test_walled_sibling_never_swapped_in(self):
        settings = {"placement": {"check_links": True}}
        free = story("Billy Crystal Says He No Longer Trusts God", source="Fox News", link="https://foxnews.com/billy")
        blaze = story("Billy Crystal No Longer Trusts God. Christians Should Listen.", source="The Blaze",
                      link="https://www.theblaze.com/columns/opinion/billy-crystal")
        self.assertFalse(A.link_free(blaze, settings))
        self.assertTrue(blaze["paywalled"])  # marked so every other swap path skips it
        blaze["paywalled"] = False; A.WALL_CACHE.clear()
        lead = story("Border Bill Passes Senate", link="https://example.com/lead")
        c = {"id": 1, "outlets": ["Fox News", "The Blaze"], "items": [free, blaze]}
        _, _, cols, _ = A.decorate_headlines(lead, [], [[free]], [c, {"id": 2, "outlets": ["x"], "items": [lead]}], settings, NOW)
        self.assertEqual(cols[0][0]["link"], "https://foxnews.com/billy")

    def test_billy_crystal_suppressed(self):
        s = A.load_settings() if hasattr(A, "load_settings") else __import__("json").load(open(A.os.path.join(A.HERE, "settings.json")))
        self.assertTrue(A.suppressed("https://www.theblaze.com/columns/opinion/billy-crystal-no-longer-trusts-god-christians-should-listen", s))


if __name__ == "__main__":
    unittest.main()
