"""Deterministic Drudge-style headline cleanup (abbreviations, filler, chrome)
plus optional display overrides from headline_overrides.json / manual pins.

Never truncates. Over-long cleaned headlines are flagged for a TRIM rewrite
(see needs_trim / decorate_headlines); they still display in full until overridden.
"""
import html as _html, json, os, re

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
        if long in t and len(t) > len(long) + 4:
            t = t.replace(long, short)
    return t


def clean(title, styl=None):
    """Apply deterministic style rules. Never truncates. Returns (display, changed)."""
    sty = styl or style()
    orig = title
    t = title.strip()
    for p in sty.get("title_prefixes", []):
        if t.startswith(p):
            t = t[len(p):].lstrip(" -–—:")
    for tag in sty.get("trailing_tags", []):
        if t.endswith(tag):
            t = t[: -len(tag)].rstrip(" -–—:")
    # strip trailing " | Outlet" / " — Outlet" when the tail is short
    for sep in sty.get("trailing_site_sep", []):
        if sep in t:
            left, right = t.rsplit(sep, 1)
            if 2 <= len(right.split()) <= 4 and len(right) <= 30:
                t = left.rstrip()
    for phrase in sty.get("filler_phrases", []):
        if t.lower().startswith(phrase.lower()):
            t = t[len(phrase):].lstrip(" :-–—")
    # drop trailing / mid parentheticals that are chrome, not the news
    if sty.get("strip_parentheticals", True):
        t = re.sub(r"\s*[\(\[][^)\]]{0,40}[\)\]]\s*$", "", t)
    for long, short in sty.get("abbreviations", []):
        t = re.sub(re.escape(long), short, t, flags=re.I)
    t = _party_abbrev(t, sty.get("party_abbrev", []))
    # Never "the SCOTUS" — strip the article before listed tokens (case-insensitive).
    for tok in sty.get("no_article_before", ["SCOTUS"]):
        t = re.sub(rf"\bthe\s+{re.escape(tok)}\b", tok, t, flags=re.I)
    t = re.sub(r"\s+", " ", t).strip(" -–—:")
    if sty.get("smart_quotes", True):
        t = smartquotes(t)
    return t, t != orig


_OPENERS = set(" \t\n([{—–-/“‘\u00a0")
_ELISIONS = ("em", "tis", "twas", "n", "cause", "til", "bout", "round", "nuff")


def smartquotes(text):
    """Straight ' and " -> curly. Decodes entities (&#39; &quot; &#x27;) first.
    Operates on plain text; escape for HTML afterwards. Idempotent."""
    if not text:
        return text
    s = _html.unescape(text) if "&" in text else text
    out = []
    n = len(s)
    for i, ch in enumerate(s):
        if ch not in "'\"":
            out.append(ch); continue
        prev = out[-1] if out else None
        nxt = s[i + 1] if i + 1 < n else None
        opening = prev is None or prev in _OPENERS
        if ch == "'":
            if not opening:
                out.append("’")                       # contraction / possessive / closing
            elif nxt and nxt.isdigit():
                out.append("’")                       # '90s
            elif any(s[i + 1:i + 1 + len(w)].lower() == w and
                     (i + 1 + len(w) >= n or not s[i + 1 + len(w)].isalpha()) for w in _ELISIONS):
                out.append("’")                       # 'em, 'tis
            elif nxt is None or nxt.isspace():
                out.append("’")
            else:
                out.append("‘")
        else:
            out.append("“" if opening and nxt is not None and not nxt.isspace() else "”")
    return "".join(out)


def smartquotes_html(markup):
    """Apply smartquotes to text nodes only (never tags/attributes/URLs)."""
    parts = re.split(r"(<[^>]*>)", markup)
    skip = False
    for k, part in enumerate(parts):
        if part.startswith("<"):
            low = part.lower()
            if low.startswith(("<script", "<style")):
                skip = True
            elif low.startswith(("</script", "</style")):
                skip = False
            continue
        if part and not skip:
            parts[k] = _html.escape(smartquotes(part), quote=False)
    return "".join(parts)


def too_long(title, styl=None):
    sty = styl or style()
    words = title.split()
    return len(title) > sty.get("max_chars", 70) or len(words) > sty.get("max_words", 12)


def needs_rewrite(title, styl=None):
    """Bland / academic / no-verb detector (does NOT include length — use too_long)."""
    sty = (styl or style()).get("rewrite_triggers", {})
    t = title.strip()
    words = t.split()
    low = t.lower()
    if any(term in low for term in sty.get("academic_terms", [])):
        return True
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
    if ":" in t and len(t) > 60:
        return True
    if sty.get("needs_verb") and not has_verb and (len(t) > 55 or len(words) > 10):
        return True
    return False


def display(story):
    url = story.get("link") or ""
    ov = overrides()
    if url in ov and ov[url]:
        return ov[url], story["title"]
    base = url.split("?", 1)[0]
    if base in ov and ov[base]:
        return ov[base], story["title"]
    cleaned, _ = clean(story["title"])
    return cleaned or story["title"], story["title"]
