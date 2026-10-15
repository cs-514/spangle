"""Internal opinion classifier (never displayed). Used to keep opinion out of the lead and to
prefer reported-news sibling headlines. An item is opinion when:
  - its feed is opinion-only, or a curator marked it (existing item["opinion"]); or
  - its URL has an opinion section (/opinion/, /commentary/, /columnists/, /blog/, /shows/, ...); or
  - an RSS category says Opinion / Commentary / Column / Op-Ed / Editorial; or
  - its outlet is mostly commentary (OUTLET_DEFAULT) and the URL has no news section; or
  - the headline shows 2+ opinion cues (rhetorical question, first person, loaded words, "Name: claim")."""
import re

URL_PATTERNS = re.compile(r"/(opinion|opinions|commentary|columnists?|columns|blog|blogs|shows|op-?eds?|editorials?|"
                          r"perspectives?|voices|analysis|ideas)(/|-)", re.I)
NEWS_PATHS = re.compile(r"/(news|us-news|world-news|politics/news|breaking)/", re.I)
CATEGORY = re.compile(r"\b(opinion|commentary|columns?|columnists?|op-?ed|editorials?)\b", re.I)
# Outlets whose pieces are mostly commentary/blog posts.
OUTLET_DEFAULT = {"RedState", "Hot Air", "PJ Media", "American Thinker", "The Federalist", "American Greatness",
                  "Townhall", "Twitchy", "Not the Bee", "Volokh Conspiracy", "Imprimis", "Hollywood in Toto"}
LOADED = re.compile(r"\b(crazy|shameless|witch hunt|hoax|horrific|commissars?|disgraceful|pathetic|insane|"
                    r"unhinged|idiotic|must be stopped|wants you|go away|let'?s|should|shouldn'?t|need to|"
                    r"the truth about|here'?s why|proof that|destroys|obliterates|wrecked|slithered|clown)\b", re.I)
FIRST_PERSON = re.compile(r"\b(i|i'm|i've|we|we're|my|our|us)\b", re.I)


def cues(title):
    t = title.replace("’", "'")
    n = 0
    if t.rstrip().endswith("?"):
        n += 1
    if FIRST_PERSON.search(t):
        n += 1
    n += min(2, len(LOADED.findall(t)))
    if re.match(r"^[A-Z][\w.'-]+(?: [A-Z][\w.'-]+){1,2}: ", t):  # "Name Surname: claim"
        n += 1
    if re.match(r"^(why|how) ", t, re.I):
        n += 1
    return n


def classify(s):
    link, title = s.get("link", ""), s.get("title", "")
    if s.get("opinion") or URL_PATTERNS.search(link) or CATEGORY.search(s.get("cats") or ""):
        return True
    outlet = (s.get("source") or "").replace(" Politics", "").replace(" Opinion", "")
    if outlet in OUTLET_DEFAULT and not NEWS_PATHS.search(link):
        return True
    return cues(title) >= 2
