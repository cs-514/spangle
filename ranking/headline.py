"""Deterministic Drudge-style headline cleanup (abbreviations, filler, chrome)
plus optional display overrides from headline_overrides.json / manual pins."""
import json, os, re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_STYLE = None
_OVERRIDES = None


def style():
    global _STYLE
    if _STYLE is None:
        with open(os.path.join(HERE, "headline_style.json")) as f:
            _STYLE = json.load(f)
    return _STYLE


def overrides():
    global _OVERRIDES
    if _OVERRIDES is None:
        path = os.path.join(HERE, "headline_overrides.json")
        try:
            with open(path) as f:
                _OVERRIDES = json.load(f) or {}
        except Exception:
            _OVERRIDES = {}
    return _OVERRIDES


def _party_abbrev(t, pairs):
    for long, short in pairs:
        # only when it clearly shortens and isn't the whole headline
        if long in t and len(t) > len(long) + 4:
            t = t.replace(long, short)
    return t


def clean(title, styl=None):
    """Apply deterministic style rules. Returns (display, changed)."""
    sty = styl or style()
    orig = title
    t = title.strip()
    for p in sty.get("title_prefixes", []):
        if t.startswith(p):
            t = t[len(p):].lstrip(" -–—:")
    for tag in sty.get("trailing_tags", []):
        if t.endswith(tag):
            t = t[: -len(tag)].rstrip(" -–—:")
    # strip trailing " | Outlet" / " — Outlet" when the tail is short and title-ish
    for sep in sty.get("trailing_site_sep", []):
        if sep in t:
            left, right = t.rsplit(sep, 1)
            if 2 <= len(right.split()) <= 4 and len(right) <= 30:
                t = left.rstrip()
    for phrase in sty.get("filler_phrases", []):
        if t.lower().startswith(phrase.lower()):
            t = t[len(phrase):].lstrip(" :-–—")
    for long, short in sty.get("abbreviations", []):
        t = re.sub(re.escape(long), short, t, flags=re.I)
    t = _party_abbrev(t, sty.get("party_abbrev", []))
    t = re.sub(r"\s+", " ", t).strip(" -–—:")
    # soft trim on word boundary if still too long
    max_c = sty.get("max_chars", 70)
    if len(t) > max_c + 10:
        cut = t[: max_c + 1]
        if " " in cut:
            t = cut.rsplit(" ", 1)[0].rstrip(",;:")
    return t, t != orig


def needs_rewrite(title, styl=None):
    sty = (styl or style()).get("rewrite_triggers", {})
    t = title.strip()
    words = t.split()
    if len(t) > sty.get("max_chars", 85) or len(words) > sty.get("max_words", 14):
        return True
    low = t.lower()
    if any(term in low for term in sty.get("academic_terms", [])):
        return True
    # verb / punch check: only flag as bland-for-missing-verb when ALSO long or academic
    verbs = {"is", "are", "was", "were", "isn't", "aren't", "has", "have", "had", "hasn't", "haven't",
             "says", "said", "wins", "won", "blocks", "blocked", "passes", "passed", "fires", "fired",
             "seizes", "seized", "slams", "slammed", "exposes", "exposed", "indicts", "indicted",
             "rules", "ruled", "orders", "ordered", "bans", "banned", "kills", "killed", "hits", "hit",
             "sues", "sued", "warns", "warned", "vows", "vowed", "backs", "backed", "rejects", "rejected",
             "approves", "approved", "confirms", "confirmed", "denies", "denied", "faces", "faced",
             "leads", "led", "beats", "beat", "defies", "defied", "blasts", "blasted", "deploys",
             "deployed", "packs", "packed", "scraps", "scrapped", "gives", "gave", "may", "will",
             "won't", "don't", "doesn't", "didn't", "can't", "prefer", "prefers", "know", "think"}
    toks = [re.sub(r"[^a-z']", "", w.lower()) for w in words]
    has_verb = any(w in verbs or (w.endswith(("ed", "ing")) and len(w) > 4)
                   or (w.endswith("s") and len(w) > 4 and w not in {"news", "times", "politics", "affairs"})
                   for w in toks)
    # colon-plus-long-subtitle is a Drudge anti-pattern worth rewriting when long
    if ":" in t and len(t) > 60:
        return True
    if sty.get("needs_verb") and not has_verb and (len(t) > 55 or len(words) > 10):
        return True
    return False


def display(story):
    """Final display headline for a story dict. Prefers override, then cleaned original."""
    url = story.get("link") or ""
    ov = overrides()
    if url in ov and ov[url]:
        return ov[url], story["title"]
    # try without query string
    base = url.split("?", 1)[0]
    if base in ov and ov[base]:
        return ov[base], story["title"]
    cleaned, _ = clean(story["title"])
    return cleaned or story["title"], story["title"]
