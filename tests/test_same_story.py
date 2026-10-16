import unittest
from _helpers import story, NOW
import aggregator as A

S = {"placement": {"check_links": False}, "originator": {"margin": 0.15},
     "clean_links": {"enabled": True, "min_gain": 0.08}, "sources": {"tiers": {}, "default_tier": 0.5},
     "age_limits": {"lead_hours": 99, "top_hours": 99, "column_hours": 99}}

MISMATCH = [
    ("Kamala Harris to Campaign for David Crowley in Wisconsin",
     "Democratic nominee for Wisconsin Secretary of State says her number one priority is giving driver's licenses to illegal aliens",
     "https://notthebee.com/article/democratic-nominee-for-wisconsin-secretary-of-state-says-her-number-one-priority/"),
    ("Talarico’s Record Is Scarier Than Halloween", "James Talarico faces Black voter frustration in Texas Senate race",
     "https://www.foxnews.com/politics/black-civic-group-blasts-talarico-campaign-canceled-event"),
    ("Getting the Second Amendment Right", "El-Sayed's radical Second Amendment stance should alarm Michigan voters",
     "https://www.foxnews.com/opinion/el-sayed-words-reveal-radical-plan-dismantle-second-amendment.amp"),
    ("Getting the Second Amendment Right", "El-Sayed's own words reveal a radical plan to dismantle the Second Amendment",
     "https://www.foxnews.com/opinion/el-sayed-words-reveal-radical-plan-dismantle-second-amendment.amp"),
    ("And This Is Why Gun Control Is a Problem", "Report: Oregon Elementary School Attacker Used Shotgun His Mom Bought",
     "https://www.breitbart.com/2nd-amendment/2026/10/15/oregon-elementary-school-attacker-shotgun-mom/amp/"),
]
SAME = [
    ("New Documents Question Key Claims From Trump’s 2019 Impeachment",
     "Impeaching Impeachment: Declassified memos challenge key witness testimony from 2019 Trump case",
     "https://justthenews.com/accountability/russia-and-ukraine-scandals/declassified-records-challenge-key-2019-trump"),
    ("Pope Leo Seen in First Photos Since Surgery and Cancer Diagnosis", "Pope Leo seen in first photos since surgery",
     "https://www.foxnews.com/world/pope-leo-first-photos"),
    ("Wall Street Suspects China Hiding U.S. Debt in Canada",
     "China may be secretly stashing US debt holdings in Canada, Wall Street analysts suspect",
     "https://nypost.com/2026/10/15/business/china-may-be-secretly-stashing-us-debt-holdings-in-canada"),
]


class SameStory(unittest.TestCase):
    def test_mismatches_rejected(self):
        for h, t, u in MISMATCH:
            self.assertFalse(A.same_story(h, {"title": t, "link": u}), h)

    def test_same_story_accepted(self):
        for h, t, u in SAME:
            self.assertTrue(A.same_story(h, {"title": t, "link": u}), h)

    def test_clean_links_keeps_own_link_for_other_story(self):
        # Kamala headline clustered with an earlier, cleaner Not the Bee post about a different Wisconsin race
        h, t, u = MISMATCH[0]
        own = story(h, hours=2, source="Washington Examiner", link="https://www.washingtonexaminer.com/kamala-crowley")
        ntb = story(t, hours=9, source="Not the Bee", link=u)
        own["display"] = own["original_title"] = h
        lead = story("Border Bill Passes Senate", link="https://example.com/lead")
        orig = A.ranking.clutter.clean_score
        A.ranking.clutter.clean_score = lambda url, default=0.5: 0.9 if "notthebee" in url else 0.3
        try:
            A.clean_links(lead, [], [[own]], [{"id": 1, "outlets": ["a", "b"], "items": [own, ntb]}], S, NOW)
        finally:
            A.ranking.clutter.clean_score = orig
        self.assertEqual(own["link"], "https://www.washingtonexaminer.com/kamala-crowley")


if __name__ == "__main__":
    unittest.main()
