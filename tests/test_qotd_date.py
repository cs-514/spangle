import json, os, tempfile, unittest
from datetime import datetime, timezone
from _helpers import ROOT  # noqa: F401  (puts the repo on sys.path)
import aggregator as A


class _Clock(datetime):
    """datetime whose now() is fixed at 01:12 UTC on Oct 20, 2026 (9:12 PM ET on Oct 19)."""
    @classmethod
    def now(cls, tz=None):
        t = datetime(2026, 10, 20, 1, 12, tzinfo=timezone.utc)
        return t.astimezone(tz) if tz else t.replace(tzinfo=None)


class EasternDate(unittest.TestCase):
    def test_evening_et_keeps_routine_pick(self):
        """After 8 PM ET the UTC date has rolled over; the routine's pick for the Eastern day must still show."""
        with tempfile.TemporaryDirectory() as d:
            json.dump({"date": "2026-10-19", "headline": "Routine Pick Stays Up", "quote": "Q.", "author": "A"},
                      open(os.path.join(d, "q.json"), "w"))
            old_here, old_dt = A.HERE, A.datetime
            A.HERE, A.datetime = d, _Clock
            try:
                q = A.load_daily_quote("q.json", bank_file="missing.json")
            finally:
                A.HERE, A.datetime = old_here, old_dt
        self.assertIsNotNone(q)
        self.assertEqual(q["headline"], "Routine Pick Stays Up")


if __name__ == "__main__":
    unittest.main()
