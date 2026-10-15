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
    t = drop_possessives(t, sty)
    t = numerals(t, sty)
    t = title_case(t, sty)
    if sty.get("smart_quotes", True):
        t = smartquotes(t)
    t = trim_quoted_labels(t, sty)
    return t, t != orig


def trim_quoted_labels(title, sty=None):
    """Concision for quoted labels (runs on curly text): ‘Muslim Brotherhood guy’ -> ‘Muslim
    Brotherhood’ when the quote has >= 2 words and ends in a generic noun; ‘kind of a joke’ ->
    ‘joke’; and drop a filler a/an right before such a trimmed quote. Conservative: only spans
    in curly quotes, and the core label must keep at least one word."""
    cfg = (sty or style()).get("trim_quoted_labels") or {}
    if not cfg.get("enabled"):
        return title
    nouns = {n.lower() for n in cfg.get("generic_nouns", [])}
    prefixes = sorted((p.lower() for p in cfg.get("generic_prefixes", [])), key=len, reverse=True)

    def fix(m):
        art, oq, body, cq = m.group(1) or "", m.group(2), m.group(3), m.group(4)
        words = body.split()
        changed = False
        if len(words) >= 2 and words[-1].lower().strip(".,!?") in nouns:
            words = words[:-1]; changed = True
        low = " ".join(words).lower()
        for p in prefixes:
            if low.startswith(p + " ") and len(words) > len(p.split()):
                words = words[len(p.split()):]; changed = True
                break
        if not changed:
            return m.group(0)
        return f"{oq}{' '.join(words)}{cq}"  # filler a/an before the label is dropped too

    pat = re.compile(r"((?<![A-Za-z])(?:an?|An?)\s+)?([‘“])([^‘’“”]{1,60}?)([’”])(?![A-Za-z])")
    return re.sub(pat, fix, title)


def drop_possessives(title, sty=None):
    """Drop a redundant possessive (her/his/their/its) before a noun when a named subject
    opens the headline. Conservative: the first word must look like a name (capitalized, not a
    generic starter), the pronoun must follow a verb-like word (not a preposition/conjunction),
    be followed by a noun (not in skip_before), and must not be the last word ('Deport Her').
    Only the first such pronoun is dropped."""
    cfg = (sty or style()).get("drop_possessives") or {}
    if not cfg.get("enabled"):
        return title
    pron = {p.lower() for p in cfg.get("pronouns", [])}
    after = {w.lower() for w in cfg.get("skip_after", [])}
    before = {w.lower() for w in cfg.get("skip_before", [])}
    generic = {w.lower() for w in cfg.get("generic_starters", [])}
    toks = title.split(" ")
    bare = lambda w: re.sub(r"[^A-Za-z’'-]", "", w)
    if len(toks) < 4 or not toks[0][:1].isupper() or bare(toks[0]).lower() in generic:
        return title
    if any(bare(w).lower() in ("he", "she", "they", "him", "them") for w in toks[:2]):
        return title
    for i in range(2, len(toks) - 1):
        w = toks[i]
        if bare(w).lower() not in pron or w != bare(w):
            continue  # must be a clean word (no punctuation/quotes attached)
        prev, nxt = bare(toks[i - 1]).lower(), toks[i + 1]
        if not prev or toks[i - 1][-1:] in ",;:—–" or prev in after or prev in pron:
            continue
        if not nxt[:1].isalpha() or bare(nxt).lower() in before or bare(nxt).lower() in after:
            continue
        return " ".join(toks[:i] + toks[i + 1:])
    return title


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
            elif re.match(r"\d\ds?(?![\d%.,])|\d\d(?=[\s,.;:!?)]|$)", s[i + 1:i + 5]) and not re.match(r"\d+%", s[i + 1:]):
                out.append("’")                       # '90s, '24
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


_FILLER = re.compile(r"\b(?:Just|Now|Officially|Actually|Literally|Even)\s+(?=\S)")
_AUX = re.compile(r"\b(?:Was|Were|Is|Are|Has Been|Have Been)\s+(?=[A-Za-z]+ed\b)")
_PREP = re.compile(r"\s(?:at|in|on|after|amid|over|during|near|from|with|despite|following|as|across|outside|inside|before|into|against|amid)\s", re.I)


def shorten(title, styl=None):
    """Deterministic, meaning-preserving trims for over-long headlines (never truncation, no ellipsis).
    Applied in order until the headline fits max_chars/max_words: parentheticals, leading article,
    filler adverbs, passive auxiliaries ("Was Convicted" -> "Convicted"), a dash/colon tail, then
    the shortest trailing prepositional phrase or comma clause that makes it fit (>= 6 words kept).
    Returns the input unchanged if nothing safe applies."""
    sty = styl or style()
    fits = lambda t: not too_long(t, sty)
    t = title.strip()
    steps = [lambda x: re.sub(r"\s*\([^)]*\)", "", x),
             lambda x: re.sub(r"^(?:A|An|The)\s+(?=\S)", "", x),
             lambda x: _FILLER.sub("", x),
             lambda x: _AUX.sub("", x)]
    for f in steps:
        if fits(t):
            break
        t = re.sub(r"\s{2,}", " ", f(t)).strip()
    if not fits(t):
        for sep in (" — ", " – ", " | ", ": "):
            if sep in t:
                left = t.split(sep, 1)[0].strip()
                if len(left.split()) >= 4 and not contentless(left):
                    t = left
                    break
    if not fits(t):
        cuts = [m.start() for m in _PREP.finditer(t)] + [m.start() for m in re.finditer(r",\s", t)]
        for pos in sorted(cuts, reverse=True):  # smallest removal first
            cand = t[:pos].rstrip(" ,;:")
            if len(cand.split()) >= 6 and fits(cand) and not contentless(cand):
                t = cand
                break
    t = t.rstrip(" ,;:")
    if t == title.strip():
        return title
    return clean(t, sty)[0] or title


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


_VERBISH = re.compile(r"(?i)\b(is|are|was|were|has|have|had|says?|said|wins?|won|gets?|got|blocks?|"
                      r"[a-z]+(ed|ing|es))\b")


def contentless(title):
    """Too short / contentless: <=3 words with no verb, or a bare proper name (every word
    capitalized, <=4 words, no verb or punctuation suggesting a claim)."""
    words = [w for w in re.split(r"\s+", (title or "").strip()) if w]
    if not words:
        return True
    has_verb = bool(_VERBISH.search(title))
    if len(words) <= 3 and not has_verb:
        return True
    if len(words) <= 4 and not has_verb and all(w[:1].isupper() for w in words) and not re.search(r"[:?!$0-9]", title):
        return True
    return False


def page_title(url, timeout=10):
    """og:title or first <h1> of the article page, or ''."""
    import urllib.request
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Spangle/1.0"})
        body = urllib.request.urlopen(req, timeout=timeout).read(400000).decode("utf-8", "ignore")
    except Exception:
        return ""
    for pat in (r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', r"<h1[^>]*>(.*?)</h1>"):
        m = re.search(pat, body, re.S | re.I)
        if m:
            return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", "", m.group(1)))).strip()
    return ""


def numerals(title, sty=None):
    """Digits for one..nine ('In One Night' -> 'In 1 Night'). Pronoun 'one' stays a word:
    'No One', 'One of Them', 'One Another', 'Someone'. Only whole words followed by another word."""
    cfg = (sty or style()).get("numerals") or {}
    if not cfg.get("enabled"):
        return title
    words = {k.lower(): v for k, v in cfg.get("words", {}).items()}
    sp = {w.lower() for w in cfg.get("skip_prev", [])}
    sn = {w.lower() for w in cfg.get("skip_next", [])}
    toks = title.split(" ")
    for i, w in enumerate(toks):
        core = w.lower()
        if core not in words or i + 1 >= len(toks):
            continue
        nxt = re.sub(r"[^a-z0-9-]", "", toks[i + 1].lower())
        prev = re.sub(r"[^a-z-]", "", toks[i - 1].lower()) if i else ""
        if not nxt or nxt in sn or prev in sp:
            continue
        if core == "one" and not toks[i + 1][:1].isalnum():
            continue
        toks[i] = words[core]
    return " ".join(toks)


def lowercase_small_words(title, sty=None):
    """Lowercase Title-Case short prepositions/articles (In, Of, To, On, At, For, A, The) except
    as the first word or right after ':', '—', '–', '|' or an opening quote. All-caps tokens are left alone,
    and 'A' is kept when it ends the line or is followed by punctuation (Plan A)."""
    cfg = (sty or style()).get("lowercase_small_words") or {}
    if not cfg.get("enabled"):
        return title
    small = {w.lower() for w in cfg.get("words", [])}
    toks = title.split(" ")
    for i in range(1, len(toks)):
        w = toks[i]
        if w.lower() not in small or w == w.lower() or (len(w) > 1 and w.isupper()):
            continue
        if toks[i - 1][-1:] in (":", "—", "–", "|", "‘", "“", "'", '"') or toks[i - 1] in ("-", "—", "–"):
            continue
        if w == "A" and (i + 1 >= len(toks) or not toks[i + 1][:1].isalnum()):
            continue
        toks[i] = w.lower()
    return " ".join(toks)


def title_case(title, sty=None):
    """AP/Chicago-style title case. Lowercase small words (a, an, the, and, but, or, nor, as, at,
    by, for, if, in, of, on, to, vs) except first/last word or after ':', '—', '–', '|' or an
    opening quote; capitalize every other lowercase word (incl. hyphen parts). Never lowercases
    words with internal capitals (acronyms, McDonald, iPhone) and keeps lowercase name particles
    before a capitalized name ('el Sayed'). 'Up' stays capitalized (phrasal particles: 'Take Up')."""
    cfg = (sty or style()).get("title_case") or {}
    if not cfg.get("enabled"):
        return title
    small = {w.lower() for w in cfg.get("small_words", [])}
    parts_ = {w.lower() for w in cfg.get("name_particles", [])}
    keep = set(cfg.get("preserve", []))
    toks = title.split(" ")
    n = len(toks)
    out = []
    for i, w in enumerate(toks):
        m = re.match(r"^([^A-Za-z0-9]*)(.*?)([^A-Za-z0-9.%’']*)$", w)
        lead, core, trail = (m.group(1), m.group(2), m.group(3)) if m else ("", w, "")
        if not core or not core[0].isalpha() or w in keep or core in keep:
            out.append(w); continue
        prev = toks[i - 1] if i else ""
        boundary = i == 0 or i == n - 1 or prev[-1:] in (":", "—", "–", "|") or prev in ("-", "—", "–") \
            or lead[-1:] in ("‘", "“", "(", "[")
        low = core.lower()
        if not boundary and low in small and (core == low or core == core.capitalize()):
            out.append(lead + low + trail); continue
        if low in parts_ and core == low and i + 1 < n and toks[i + 1][:1].isupper():
            out.append(w); continue  # el Sayed, bin Salman
        if core != low:  # has capitals already (Title, ACRONYM, McDonald, iPhone): keep
            out.append(w); continue
        cap = "-".join(p[:1].upper() + p[1:] for p in core.split("-"))
        out.append(lead + cap + trail)
    return " ".join(out)
