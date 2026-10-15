import json, unittest, copy
from _helpers import ROOT, NOW, story
import aggregator as A


def settings():
    s = json.load(open(f"{ROOT}/settings.json"))
    s["placement"].update(check_links=False, top_stories=2, column_items=6, columns=3, max_per_outlet_top=9, max_per_outlet_total=9)
    s["manual_links"]["enabled"] = False
    s["archive"]["enabled"] = False
    s["lead"] = {"enabled": False}
    return s


def clusters(items):
    return [dict(id=i, items=[x], outlets={x["source"]}, score=1 - i / 100) for i, x in enumerate(items)]


class AgeLimits(unittest.TestCase):
    def test_fits(self):
        s = settings()
        self.assertTrue(A.fits(story("a", 11), "lead", s, NOW))
        self.assertFalse(A.fits(story("a", 13), "lead", s, NOW))
        self.assertTrue(A.fits(story("a", 17), "top", s, NOW))
        self.assertFalse(A.fits(story("a", 19), "top", s, NOW))
        self.assertTrue(A.fits(story("a", 35), "column", s, NOW))
        self.assertFalse(A.fits(story("a", 37), "column", s, NOW))
        undated = story("u", None)
        self.assertFalse(A.fits(undated, "lead", s, NOW))
        self.assertFalse(A.fits(undated, "top", s, NOW))
        self.assertTrue(A.fits(undated, "column", s, NOW))

    def test_place_respects_slots(self):
        items = [story("Old lead candidate", 25), story("Undated big story", None), story("Fresh 2", 2),
                 story("Mid 15", 15), story("Older 20", 20), story("Fresh 1", 1), story("Too old 40", 40),
                 story("Col 30", 30)]
        lead, top, cols = A.place(clusters(items), settings(), {"now": NOW})
        self.assertEqual(lead["title"], "Fresh 2")
        self.assertEqual([x["title"] for x in top], ["Mid 15", "Fresh 1"])
        flat = [x["title"] for c in cols for x in c]
        self.assertNotIn("Too old 40", flat)
        self.assertIn("Undated big story", flat)
        self.assertIn("Old lead candidate", flat)

    def test_lifestyle_capped_and_kept_out_of_front(self):
        items = [story(f"Celeb {i}", 1, lifestyle=True) for i in range(5)] + [story(f"News {i}", 2) for i in range(8)]
        cl = clusters(items)
        for c in cl:
            c["lifestyle"] = c["items"][0].get("lifestyle", False)
        lead, top, cols = A.place(cl, settings(), {"now": NOW})
        self.assertFalse(lead.get("lifestyle"))
        self.assertFalse(any(x.get("lifestyle") for x in top))
        for c in cols:
            self.assertLessEqual(sum(1 for x in c if x.get("lifestyle")), 1)


if __name__ == "__main__":
    unittest.main()


class MonthlyReserved(unittest.TestCase):
    def imp(self, title, hours):
        return story(title, hours, source="Imprimis", opinion=True, column_age_hours=840, no_front=True, reserved_slot=True,
                     link="https://imprimis.hillsdale.edu/" + title.lower().replace(" ", "-") + "/")

    def test_window_and_slots(self):
        s = settings()
        cur, old = self.imp("The Rise of Democratic Socialism", 24 * 10), self.imp("Why We Shouldn't Cancel the Supreme Court", 24 * 44)
        self.assertTrue(A.fits(cur, "column", s, NOW))
        self.assertFalse(A.fits(old, "column", s, NOW))
        self.assertFalse(A.fits(self.imp("Fresh Imprimis", 1), "lead", s, NOW))
        self.assertFalse(A.fits(self.imp("Fresh Imprimis", 1), "top", s, NOW))

    def test_reserved_slot_reaches_columns(self):
        news = [story(f"News {i}", 1 + i / 10) for i in range(20)]  # fills every slot
        cur, old = self.imp("The Rise of Democratic Socialism", 24 * 10), self.imp("Old Archive Piece", 24 * 44)
        lead, top, cols = A.place(clusters(news + [old, cur]), settings(), {"now": NOW})
        flat = [x["title"] for c in cols for x in c]
        self.assertIn("The Rise of Democratic Socialism", flat)
        self.assertNotIn("Old Archive Piece", flat)
        self.assertNotEqual(lead["source"], "Imprimis")
        self.assertFalse(any(x["source"] == "Imprimis" for x in top))
