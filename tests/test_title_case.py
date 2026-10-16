import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ranking.headline import clean, title_case


class TitleCase(unittest.TestCase):
    def test_examples(self):
        self.assertEqual(clean("DOGE Gets Its Day at the Supreme Court As Justices Take Up Trump Administration Appeal")[0],
                         "DOGE Gets Day at SCOTUS as Justices Take Up Trump Administration Appeal")
        self.assertEqual(title_case("Netanyahu rival vows to end Hamas rule within 18 months if elected"),
                         "Netanyahu Rival Vows to End Hamas Rule Within 18 Months if Elected")
        self.assertEqual(clean("Netflix to lay off 1,000 employees")[0], "Netflix to Lay Off 1,000 Employees")

    def test_preserve(self):
        self.assertEqual(clean("Trump says Abdul el Sayed is ‘100%’ a ‘Muslim Brotherhood guy’")[0],
                         "Trump Says Abdul el Sayed Is ‘100%’ ‘Muslim Brotherhood’")
        self.assertEqual(clean("McDonald slams iPhone ban by DEMS and GOP")[0], "McDonald Slams iPhone Ban by Dems and GOP")
        self.assertEqual(title_case("the end of an era"), "The End of an Era")       # first word
        self.assertEqual(title_case("what are they fighting for"), "What Are They Fighting For")  # last word
        self.assertEqual(title_case("Trump: the comeback"), "Trump: The Comeback")    # after colon
        self.assertEqual(title_case("ICE says no to live-stream rules"), "ICE Says No to Live-Stream Rules")
        self.assertEqual(title_case("Gov. won’t back down"), "Gov. Won’t Back Down")

class SentenceStart(unittest.TestCase):
    def test_after_sentence_punct(self):
        self.assertEqual(title_case(". . . Abortions. but Why?"), ". . . Abortions. But Why?")
        self.assertEqual(title_case("It Failed. but why?"), "It Failed. But Why?")
        self.assertEqual(title_case("Really? the answer is no"), "Really? The Answer Is No")
        self.assertEqual(title_case("Stop! in the name of love"), "Stop! In the Name of Love")
        self.assertEqual(title_case("Trump: as expected"), "Trump: As Expected")
        self.assertEqual(title_case("He said no. “if they come, we fight”"), "He Said No. “If They Come, We Fight”")

    def test_to_always_lowercase(self):
        self.assertEqual(title_case("James Talarico Says He Wants To See Fewer Abortions. But Why?"),
                         "James Talarico Says He Wants to See Fewer Abortions. But Why?")
        self.assertEqual(title_case("Zelensky Vows To Fight On"), "Zelensky Vows to Fight On")
        self.assertEqual(title_case("Something To Look Forward To"), "Something to Look Forward to")
        self.assertEqual(title_case("To the moon"), "To the Moon")
        self.assertEqual(title_case("It Failed. to be fair"), "It Failed. To Be Fair")

    def test_embedded_quote_punct(self):
        self.assertEqual(title_case("He Asked ‘Why?’ and Walked Out"), "He Asked ‘Why?’ and Walked Out")
        self.assertEqual(title_case("Crowd Chants “Fight!” as Rally Ends"), "Crowd Chants “Fight!” as Rally Ends")

    def test_no_false_boundaries(self):
        self.assertEqual(title_case("U.S. and China talk"), "U.S. and China Talk")
        self.assertEqual(title_case("Mr. and Mrs. Smith"), "Mr. and Mrs. Smith")
        self.assertEqual(title_case("Protest in D.C. as crowds grow"), "Protest in D.C. as Crowds Grow")
        self.assertEqual(title_case("Wait . . . and then the end"), "Wait . . . and Then the End")
        self.assertEqual(title_case("Wait... and see"), "Wait... and See")


if __name__ == "__main__":
    unittest.main()
