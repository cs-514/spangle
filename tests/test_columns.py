import unittest
from _helpers import story
import aggregator as A

S = {"placement": {"quote_of_the_day": {"enabled": True, "column": 1, "index": 7},
                   "column_balance": {"chars_per_line": 40, "line_px": 27, "item_base_px": 47, "qotd_px": 245}}}


def items(lengths):
    out = []
    for i, n in enumerate(lengths):
        s = story(f"t{i}", link=f"https://e.com/{i}")
        s["display"] = " ".join(["word"] * (n // 5))
        out.append(s)
    return out


def heights(cols, cfg=S["placement"]["column_balance"], qcol=1):
    return [sum(A.item_height(x, cfg) for x in c) + (245 if i == qcol else 0) for i, c in enumerate(cols)]


class Balance(unittest.TestCase):
    def test_wrap_estimate(self):
        cfg = S["placement"]["column_balance"]
        self.assertEqual(A.item_height({"display": "Jewish Support for Dems Falls"}, cfg), 74)
        self.assertEqual(A.item_height({"display": "x " * 30}, cfg), 101)
        self.assertEqual(A.item_height({"display": "Mamdani Leads New York Dems in Demanding Parking Lot Owners Ban ICE Now"}, cfg), 101)

    def test_balanced_by_height_not_count(self):
        its = items([110, 110, 110, 110, 30, 30, 30, 30, 60] * 5)
        n = len(its) // 3
        naive = [its[i * n:(i + 1) * n] for i in range(3)]   # old: contiguous split by count
        new = A.balance_columns(naive, S)
        hn, hb = heights(naive), heights(new)
        self.assertLess(max(hb) - min(hb), max(hn) - min(hn))
        self.assertLessEqual(max(hb) - min(hb), 130)
        self.assertEqual(sorted(id(x) for c in new for x in c), sorted(id(x) for x in its))  # nothing lost

    def test_qotd_column_gets_fewer_items(self):
        its = items([60] * 45)
        new = A.balance_columns([its[:15], its[15:30], its[30:]], S)
        self.assertLess(len(new[1]), len(new[0]))

    def test_lifestyle_stays_low(self):
        its = items([60] * 12)
        its[1]["lifestyle"] = True
        new = A.balance_columns([its[:4], its[4:8], its[8:]], S)
        col = next(c for c in new if its[1] in c)
        self.assertIs(col[-1], its[1])

    def test_rank_order_roughly_top_down(self):
        its = items([60] * 30)
        new = A.balance_columns([its[:10], its[10:20], its[20:]], S)
        self.assertIn(its[0], [c[0] for c in new]); self.assertIn(its[1], [c[0] for c in new])


if __name__ == "__main__":
    unittest.main()
