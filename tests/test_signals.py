import unittest
from _helpers import story
from ranking import retreat, lean, framing, lifestyle


class Retreat(unittest.TestCase):
    A, V, B = ["trump"], ["backs down", "caves", "walks back"], ["judge", "court", "democrats"]

    def test_actor_retreat(self):
        self.assertTrue(retreat._hit("Trump backs down on tariffs", self.A, self.V, 8, self.B))

    def test_court_is_subject(self):
        self.assertFalse(retreat._hit("Judge caves to Trump on tariffs", self.A, self.V, 8, self.B))


class Lean(unittest.TestCase):
    def setUp(self):
        lean._CFG = None
        self.s = {"lean_filter": {"threshold": 1, "sources": {"RCP": "right_only"},
                                  "right_terms": ["border security"], "left_terms": ["climate justice"]}}

    def tearDown(self):
        lean._CFG = None

    def test_modes(self):
        self.assertTrue(lean.keep(story("Anything at all"), "Other", self.s))
        self.assertTrue(lean.keep(story("Why border security wins"), "RCP", self.s))
        self.assertFalse(lean.keep(story("The case for climate justice"), "RCP", self.s))


class Framing(unittest.TestCase):
    def test_subject_negative(self):
        st, se = ["faces lawsuit", "accused of", "indicted"], ["gaetz", "trump"]
        self.assertTrue(framing._neg("matt gaetz faces lawsuit over scheme", [], [], 6, None, st, se))
        self.assertFalse(framing._neg("trump doj: comey indicted", [], [], 6, None, st, se))
        self.assertFalse(framing._neg("trump sues the new york times", [], [], 6, None, st, se))


class Lifestyle(unittest.TestCase):
    T, H = ["nfl", "kelce", "celebrity", "motherhood"], ["trans", "trump"]

    def test_flag_and_hooks(self):
        self.assertTrue(lifestyle.flag("Travis Kelce Opens Up About Season", self.T, self.H))
        self.assertFalse(lifestyle.flag("Trans Athlete Wins Girls' NFL Flag Title", self.T, self.H))
        self.assertFalse(lifestyle.flag("Senate Passes Border Bill", self.T, self.H))


if __name__ == "__main__":
    unittest.main()
