"""Story identity checks shared by link verification and the social signals.
same_story(headline, item): would `item` (title + URL slug) still be the same article as `headline`?
opposed(a, b): do two headlines describe opposite actions (waives vs imposes)?"""
import re, urllib.parse


_STOP = set("""from that with says said will about after over their they this what more than into been have were
when where your just could would should also only being here there them then some most such these those which while
amid""".split())


def _words(t):
    t = t.lower().replace("’", "'")
    t = re.sub(r"'s\b", "", t)
    return {w for w in re.findall(r"[a-z0-9]+", t) if (len(w) > 3 or w.isdigit()) and w not in _STOP}


def same_story(headline, x, min_overlap=0.34):
    """Would linking item x under `headline` still be the same article topic? Content-word overlap between
    the headline and x's title + URL slug, as a share of the smaller set. Mis-clustered siblings (e.g. a
    Harris rally headline on a Wisconsin secretary-of-state story) fall well below; rewrites of the same
    report stay above. When unsure, callers keep the headline's own link."""
    a = _words(headline)
    slug = urllib.parse.urlparse(x["link"]).path.replace("-", " ").replace("/", " ")
    b = _words(f"{x['title']} {slug}")
    if not a or not b:
        return False
    shared, ratio = len(a & b), len(a & b) / min(len(a), len(b))
    if ratio < min_overlap or (shared < 3 and ratio < 0.6):  # two shared generic words ('democrats', 'problem') aren't enough
        return False
    # Sentence-case titles (Fox, NY Post, ...) mark names with capitals: a named subject the headline never
    # mentions means a different article (El-Sayed's 2A stance is not "Getting the Second Amendment Right").
    toks = re.findall(r"[A-Za-z][\w'’.-]*", x["title"])
    if toks and sum(t[0].isupper() for t in toks) / len(toks) < 0.6:
        lead_name = lambda t: bool(re.search(r"['’]s$|^[A-Z][a-z]+-[A-Z]", t))  # El-Sayed's, O'Rourke's opening a title
        names = {w for i, t in enumerate(toks) if (i or lead_name(t)) and t[0].isupper() and not re.search(r"[:.?!]$", toks[i - 1])
                 for w in _words(t) if w not in _GENERIC_CAPS}
        if names and not names & a:
            return False
    return True


_GENERIC_CAPS = {"second", "amendment", "first", "supreme", "court", "senate", "house", "congress", "democrats",
                 "democratic", "republicans", "republican", "white", "state", "states", "united", "federal", "american"}



# Opposite action verbs: a story that relaxes something is not the same story as one that imposes it,
# however many words they share ("Trump Waives Russia Sanctions" vs "Trump Signs Order Putting New Sanctions").
RELAX = re.compile(r"\b(waiv(e|es|ed|ing|er)|lift(s|ed|ing)?|drop(s|ped|ping)?|paus(e|es|ed|ing)|delay(s|ed|ing)?|"
                   r"eas(e|es|ed|ing)|suspend(s|ed|ing)?|exempt(s|ed|ing|ion)?|rescind(s|ed)?|revok(e|es|ed)|repeal(s|ed)?|"
                   r"halt(s|ed)?|scrap(s|ped)?|cancel(s|ed|led)?|relax(es|ed)?|loosen(s|ed)?|roll(s|ed)? back|"
                   r"back(s|ed)? off|walk(s|ed)? back|retreat(s|ed)?|softens?|cuts? off)\b", re.I)
IMPOSE = re.compile(r"\b(impos(e|es|ed|ing)|sign(s|ed|ing)?|order(s|ed|ing)?|add(s|ed|ing)?|expand(s|ed|ing)?|"
                    r"slap(s|ped)?|hik(e|es|ed)|tighten(s|ed)?|toughen(s|ed)?|put(s|ting)?|plac(e|es|ed|ing)|"
                    r"extend(s|ed)?|ramp(s|ed)? up|escalat(e|es|ed)|new|more|enforc(e|es|ed)|launch(es|ed)?)\b", re.I)


def opposed(a, b):
    """True when one side relaxes and the other (with no relax verb of its own) imposes/acts."""
    ra, rb = bool(RELAX.search(a or "")), bool(RELAX.search(b or ""))
    return (ra and not rb and bool(IMPOSE.search(b or ""))) or (rb and not ra and bool(IMPOSE.search(a or "")))
