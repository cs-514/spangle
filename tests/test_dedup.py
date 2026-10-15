import unittest
from _helpers import story
from ranking import coverage


def run(titles, filler=60):
    items = [story(t, 1, source=f"Outlet {i}") for i, t in enumerate(titles)]
    # background corpus so document frequencies look like a real day
    items += [story(f"Unrelated headline number {i} about topic{i} and matter{i}", 1, source="Bg") for i in range(filler)]
    return coverage.cluster(items, 0.5)


def group_of(cl, title):
    return next(c["id"] for c in cl for s in c["items"] if s["title"] == title)


class Dedup(unittest.TestCase):
    def test_same_person_story_merges(self):
        t = ["Ultimate Aim of Ilhan Omar Probe Is to Strip Her Citizenship",
             "Feds subpoena Ilhan Omar's family, seize her phone in raid",
             "Ilhan Omar passport seized as probe widens, report says",
             "Liberal lawyer says the Omar immigration probe is legitimate"]
        cl = run(t)
        self.assertEqual(len({group_of(cl, x) for x in t}), 1)

    def test_same_event_different_words(self):
        t = ["FBI probes suspicious white powder letters sent to Dem senators nationwide",
             "Letters with 'suspicious powder' sent nationwide, including to congressional offices"]
        cl = run(t)
        self.assertEqual(group_of(cl, t[0]), group_of(cl, t[1]))

    def test_unrelated_stay_apart(self):
        t = ["Bill Clinton campaigns in Georgia for Senate hopeful",
             "Hillary Clinton slams new book in interview",
             "Atlanta police release new video of carjacking suspect",
             "Court to hear argument on video privacy law"]
        cl = run(t)
        self.assertEqual(len({group_of(cl, x) for x in t[:2]}), 2)
        self.assertNotEqual(group_of(cl, t[2]), group_of(cl, t[3]))


if __name__ == "__main__":
    unittest.main()
