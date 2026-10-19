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


class ShortPrepositions(unittest.TestCase):
    def tc(self, s):
        from ranking import headline as H
        return H.title_case(s)

    def test_with_from_into_onto_upon_lowercase(self):
        self.assertEqual(self.tc("Ken Paxton Partied With Fugitives in Dubai"), "Ken Paxton Partied with Fugitives in Dubai")
        self.assertEqual(self.tc("Pirro Opens Probe Into Omar"), "Pirro Opens Probe into Omar")
        self.assertEqual(self.tc("Boot Judge From Trump’s Fight"), "Boot Judge from Trump’s Fight")
        self.assertEqual(self.tc("Rides Onto Stage Upon Request"), "Rides onto Stage upon Request")

    def test_boundaries_keep_capital(self):
        self.assertEqual(self.tc("With Friends Like These"), "With Friends Like These")
        self.assertEqual(self.tc("Crime: With Friends"), "Crime: With Friends")
        self.assertEqual(self.tc("Who Is He With?"), "Who Is He With?")
        self.assertEqual(self.tc("He Lied. With Gusto"), "He Lied. With Gusto")

    def test_over_preposition_vs_particle(self):
        self.assertEqual(self.tc("Sues Governor Over Eligibility Rule"), "Sues Governor over Eligibility Rule")
        self.assertEqual(self.tc("Fight Over $1M Deal"), "Fight over $1M Deal")
        self.assertEqual(self.tc("Musk Takes Over Twitter"), "Musk Takes Over Twitter")
        self.assertEqual(self.tc("Trump Hands Over Files"), "Trump Hands Over Files")
        self.assertEqual(self.tc("Game Over for Biden"), "Game Over for Biden")
        self.assertEqual(self.tc("Fight Over, Says Trump"), "Fight Over, Says Trump")

    def test_adverbs_untouched(self):
        self.assertEqual(self.tc("Trump Fires Back at Critics"), "Trump Fires Back at Critics")
        self.assertEqual(self.tc("Fed Shuts Down Bank"), "Fed Shuts Down Bank")

    def test_overrides_are_cleaned_to_rule(self):
        # override values pass through clean() at display time, so a capitalized 'With' in the data self-heals
        self.assertEqual(clean("Trump Feuds With Rivals Over Rule")[0], "Trump Feuds with Rivals over Rule")
