import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ranking import headline as H


class Compress(unittest.TestCase):
    def test_example(self):
        self.assertEqual(H.clean("The Power to Tax Involves the Power to Destroy")[0], "Power to Tax, Power to Destroy")

    def test_leading_article(self):
        self.assertEqual(H.clean("The FBI Raids Home of Ex-Official")[0], "FBI Raids Home of Ex-Official")
        self.assertEqual(H.clean("A Judge Blocks Trump Order")[0], "Judge Blocks Trump Order")
        self.assertEqual(H.clean("The Hill Reports Senate Deal")[0], "The Hill Reports Senate Deal")  # a name

    def test_keeps_verbs_and_iconic_lines(self):
        for t in ["Trump Says Deal Means Lower Prices for Everyone", "Mr. Gorbachev, Tear Down This Wall!",
                  "Supreme Excellence Against Adversaries", "The Almighty Has His Own Purposes",
                  "Senate Passes Border Bill"]:
            self.assertEqual(H.clean(t)[0], t)
