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


def strip_tracking(url):
    """Drop utm_* (and similar campaign) query params; keep any other query and the fragment."""
    if "?" not in url:
        return url
    from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
    p = urlsplit(url)
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if not k.lower().startswith("utm_")]
    return urlunsplit(p._replace(query=urlencode(q)))


class _Overrides(dict):
    """URL -> headline. A key may also be "sha256:<hex of the URL>" so a URL that names a
    private-list figure need not appear in the public repo (see url_key). Keys saved with utm params
    also match the stripped URL the feeds now produce."""
    def __init__(self, d):
        super().__init__(d)
        for k, v in list(d.items()):
            sk = strip_tracking(k) if k.startswith("http") else k
            if sk != k and not dict.__contains__(self, sk):
                dict.__setitem__(self, sk, v)
    def _k(self, url):
        return url if dict.__contains__(self, url) else url_key(url)
    def __contains__(self, url):
        return dict.__contains__(self, url) or dict.__contains__(self, url_key(url))
    def __getitem__(self, url):
        return dict.__getitem__(self, self._k(url))
    def get(self, url, default=None):
        return dict.get(self, self._k(url), default)


def url_key(url):
    import hashlib
    return "sha256:" + hashlib.sha256(url.encode()).hexdigest()


def overrides():
    global _OVERRIDES
    if _OVERRIDES is None:
        path = os.path.join(HERE, "headline_overrides.json")
        try:
            with open(path) as f:
                raw = json.load(f) or {}
            if not isinstance(raw, dict):
                raise ValueError("not an object")
        except Exception as ex:  # a broken overrides file must never block a deploy
            print(f"overrides: unreadable ({type(ex).__name__}); building without overrides")
            raw = {}
        from .override_lint import sanitize
        good, dropped = sanitize(raw)
        if dropped:
            print(f"overrides: dropped {len(dropped)} invalid entries")
        _OVERRIDES = _Overrides(good)
    return _OVERRIDES


def _party_abbrev(t, pairs):
    for long, short in pairs:
        if long in t and len(t) > len(long) + 4:
            t = t.replace(long, short)
    return t


def acronyms(sty=None, kind="all"):
    """The acronym lists in headline_style.json: "well_known" (fine in headlines) and "case_only" (keep the
    casing, but a headline using one is queued as obscure). kind: "all", "well_known" or "case_only"."""
    a = (sty or style()).get("acronyms") or {}
    if isinstance(a, list):  # legacy flat list
        return set(a) if kind != "case_only" else set()
    if kind == "all":
        return set(a.get("well_known", [])) | set(a.get("case_only", []))
    return set(a.get(kind, []))


_ROMAN = {"II", "III", "IV", "VI", "VII", "VIII", "IX", "XI", "XII", "XIV", "XV", "XX", "LVIII", "LIX", "LX", "LXI", "LXII", "OK"}


_POSTAL = set("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND "
               "OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split())


def obscure_acronyms(title, sty=None):
    """ALL-CAPS tokens in a display headline that a general national reader may not recognize: anything
    not in acronyms.well_known (SJSU, NRSC, DSA, CENTCOM). Hyphen parts are checked on their own
    (Ex-SJSU, AI-Generated); dotted forms must be listed dotted (U.S., S.C.); possessives are ignored
    (CFA’s -> CFA); Roman numerals, single letters, number-letter tokens (F-35, $275K, Q3), phrases in
    well_known_phrases (MS Now) and 2-letter initials before a name (JD Vance) are skipped."""
    sty = sty or style()
    acr = (sty.get("acronyms") or {}) if isinstance(sty.get("acronyms"), dict) else {}
    well = acronyms(sty, "well_known")
    t = (title or "").replace("’", "'")
    for ph in acr.get("well_known_phrases", []):
        t = t.replace(ph, " ")
    toks = re.findall(r"[A-Za-z0-9.&+'\-]+", t)
    ok = lambda x: x in well or x + "." in well
    out = []
    for n, raw in enumerate(toks):
        tok = re.sub(r"(?<=[0-9A-Z])s$", "", re.sub(r"'s$|'$", "", raw)).strip("-+'")  # CFA's, AR-15s, EVs
        if ok(tok) or ok(tok.rstrip(".")):
            continue
        nxt = toks[n + 1] if n + 1 < len(toks) else ""
        for part in tok.split("-"):
            p = part.rstrip(".+")
            bare = p.replace(".", "")
            if len(bare) < 2 or not bare.isalpha() or not bare.isupper() or bare in _ROMAN:
                continue
            if ok(p) or ok(part) or (bare.endswith("S") and bare[:-1] in well):
                continue
            if (len(bare) <= 2 or "." in p) and bare not in _POSTAL and "-" not in tok \
                    and nxt[:1].isupper() and nxt[1:2].islower():
                continue  # initials before a name: JD Vance, RJ Mitte, M.D. Kittle
            out.append(p)
    return list(dict.fromkeys(out))


def fix_allcaps(title, sty=None):
    """Only true acronyms stay ALL CAPS. Known shouting forms are mapped (DEMS -> Dems, SEC/STATE ->
    Sec. of State); other all-caps words of 4+ letters (BIG MONEY, EVISCERATES) and common short words
    (BIG, NEW, NOT) become Title Case. Short unknown tokens (2-3 letters) are assumed to be acronyms."""
    sty = sty or style()
    acr = acronyms(sty)
    words = sty.get("allcaps_words", {})
    common = set(sty.get("allcaps_common", []))

    def keep(p):  # a known acronym (or its plural), or 3+ consonant-only letters (SJSU-style initialisms, NFL)
        return p in acr or (p.rstrip("S") in acr and len(p) <= 6) or (len(p) >= 3 and not re.search(r"[AEIOU]", p))

    def part(p):
        if p in words:
            return words[p]
        if keep(p):
            return p
        if p in common or len(p) >= 4:
            return p[:1] + p[1:].lower()
        return p

    def fix(m):
        lead, w, trail = m.group(1), m.group(2), m.group(3)
        if w in words:
            return lead + words[w] + trail
        if keep(w):
            return m.group(0)
        if "-" in w:  # each part of a compound on its own: EX-SJSU -> Ex-SJSU, MS-13 stays
            ps = w.split("-")
            return lead + "-".join(p if keep(p) else (p[:1] + p[1:].lower() if len(p) > 1 else p) for p in ps) + trail
        if w in common or len(w) >= 4:
            return lead + w[:1] + w[1:].lower() + trail
        return m.group(0)
    return re.sub(r"(^|[\s‘“(\[—–-])([A-Z][A-Z/\-]*[A-Z])(?=([’'s]*)(?:[\s:;,.!?’”)\]—–]|$))()", lambda m: fix(_M(m)), title)


class _M:
    def __init__(self, m):
        self._m = m
    def group(self, i):
        return self._m.group(0) if i == 0 else (self._m.group(1), self._m.group(2), "")[i - 1]


_EN_RANGE = re.compile(r"(?<=\d)\s*–\s*(?=\d)")


def dashes(text, closed=True):
    """House dash style: a dash between words or clauses is a closed em dash ('Watch List—As He Insists').
    '--', '—' with or without spaces and a spaced en dash ' – ' all become '—'. Number ranges keep their en
    dash, closed ('10 – 12' -> '10–12'); hyphens and unspaced en dashes between words are left alone.
    closed=False gives the spaced internal form ' — ' that the other headline rules split on."""
    if not text:
        return text
    t = _EN_RANGE.sub("–", text)
    t = re.sub(r"(?<!-)-{2,3}(?!-)", "—", t)          # '--' and '---', spaced or not
    t = re.sub(r"(?<=\S)\s+–\s+(?=\S)", "—", t)      # spaced en dash used as a dash
    t = re.sub(r"\s*—\s*", "—" if closed else " — ", t)
    return t if closed else t.strip()


def open_dashes(text):
    """'A—B' -> 'A — B' so word-level rules (tokens, title case, separators) see the dash as a break."""
    return re.sub(r"\s*—\s*", " — ", text or "")


def clean(title, styl=None):
    """Apply deterministic style rules. Never truncates. Returns (display, changed)."""
    sty = styl or style()
    orig = title
    t = _EN_RANGE.sub("–", title.strip())  # '10 – 12' is a range, not an outlet separator
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
    # dashes: outlet/prefix stripping above matched the source's own separators; from here the rules see
    # one spaced form ' — ' and the result is closed again at the end ('List—As He Insists')
    t = dashes(t, closed=False)
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
    t = fix_allcaps(t, sty)
    t = title_case(t, sty)
    if sty.get("smart_quotes", True):
        t = smartquotes(t)
    t = trim_quoted_labels(t, sty)
    t = compress(t, sty)
    if sty.get("single_quotes", True):
        t = headline_quotes(smartquotes(t))  # headlines quote with ‘…’ (nested “…”); QOTD bodies never pass here
    if sty.get("closed_em_dash", True):
        t = dashes(t)
    return t, t != orig


def compress(title, sty=None):
    """Conservative compression (style "compression"): drop a leading article (The/A/An) unless the
    next word starts a protected name ("The Hill", "The Atlantic"), and turn "X Involves/Means/Equals Y"
    into "X, Y" only when both sides are short noun phrases with no other verb. Never touches action
    verbs, questions or quotes."""
    cfg = (sty or {}).get("compression") or {}
    if not cfg.get("enabled", True):
        return title
    t = title
    protect = [p.lower() for p in cfg.get("protect_after_article", [])]
    m = re.match(r"(The|A|An)\s+(\S+)(.*)$", t)
    if m and len(t.split()) >= 4 and not t.endswith("?"):
        nxt = (m.group(2) + m.group(3)).lower()
        if not any(nxt.startswith(p) for p in protect) and m.group(2)[:1].isalpha() \
                and not re.match(r"[‘“'\"]", m.group(2)):
            t = m.group(2)[:1].upper() + m.group(2)[1:] + m.group(3)
    link = cfg.get("linking_verbs", ["Involves", "Means", "Equals"])
    m = re.match(r"^(.{3,40}?)\s+(" + "|".join(map(re.escape, link)) + r")\s+(?:the\s+|The\s+)?(.{3,40})$", t)
    if m and not re.search(r"[:?!‘“\"]", t) and ',' not in t:
        left, right = m.group(1), m.group(3)
        lw, rw = left.split(), right.split()
        if len(lw) <= 5 and len(rw) <= 5 and lw[0].lower() == rw[0].lower():  # parallel noun phrases only
            t = f"{left}, {right[:1].upper() + right[1:]}"
    return t


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


def _poss(x):
    return x + ("’" if x.endswith("s") and not x.endswith("ss") else "’s")


def imprimis_recast(title):
    """Deterministic fallback for Imprimis lecture-style titles (used only when no override exists):
    put the subject first as a possessive, drop articles. 'The Rise of Democratic Socialism' ->
    'Democratic Socialism’s Rise'; 'The Hard Truth About the Sanctuary Movement' -> 'Sanctuary
    Movement’s Hard Truth'; 'Recovering the Lost Art of Diplomacy' -> 'Diplomacy’s Lost Art'.
    Anything it can't recast safely is returned unchanged (the rewrite queue handles it)."""
    t = title.strip()
    art = r"(?:(?:the|a|an)\s+)?"
    subj = r"([A-Z][\w’'.\-–]*(?:\s+[A-Z][\w’'.\-–]*){0,3})"   # 1-4 capitalized words, not a clause
    rules = [
        (rf"^(?:Recovering|Reviving|Restoring)\s+the\s+(Lost\s+Art|Forgotten\s+\w+)\s+of\s+{art}{subj}$", lambda m: f"{_poss(m[2])} {m[1]}"),
        (rf"^{art}((?:[A-Z]\w+\s+)?[A-Z]\w+)\s+(?:About|Behind)\s+{art}{subj}$", lambda m: f"{_poss(m[2])} {m[1]}"),
        (rf"^{art}([A-Z]\w+)\s+of\s+{art}{subj}$", lambda m: f"{_poss(m[2])} {m[1]}"),
        (rf"^Learning\s+[Ff]rom\s+{subj}$", lambda m: f"Lessons of {m[1]}"),
        (rf"^(?:Understanding|How\s+to\s+Think\s+About)\s+{art}{subj}$", lambda m: f"Rethinking {m[1]}"),
    ]
    for rx, f in rules:
        m = re.match(rx, t, flags=re.I if False else 0)
        if m and not re.match(r"^[A-Z]\w+ing\b", m[m.lastindex]):  # 'The Dangers of Undermining …' stays
            out = f(m)
            if 2 <= len(out.split()) <= 6:
                return out
    return t


def headline_quotes(text):
    """Headline style: quotations take single curly quotes; a quote nested inside one takes double.
    Expects curly text (run smartquotes first). “Affordability” -> ‘Affordability’;
    “He said ‘no’” -> ‘He said “no”’. Apostrophes (Dems’, don’t, ’90s) are left alone."""
    if not text or not any(c in text for c in "“”‘"):
        return text
    out, depth, single_open, outer = [], 0, 0, 0  # outer: already-single outer quotes (house style)
    for i, ch in enumerate(text):
        prev, nxt = text[i - 1:i], text[i + 1:i + 2]
        if not depth and ch == "‘":
            outer += 1; out.append(ch); continue
        if not depth and outer and ch == "’" and not (prev.isalpha() and nxt.isalpha()) and not nxt.isdigit():
            outer -= 1; out.append(ch); continue
        if outer and not depth and ch in "“”":
            out.append(ch); continue  # nested double inside a single quote: already correct
        if ch == "“":
            depth += 1; out.append("‘")
        elif ch == "”" and depth:
            depth -= 1; out.append("’")
        elif ch == "‘" and depth:
            single_open += 1; out.append("“")
        elif ch == "’" and depth and single_open:
            if prev.isalpha() and nxt.isalpha():
                out.append(ch)  # don’t
            else:
                single_open -= 1; out.append("”")
        elif ch == "”":
            out.append("’")  # stray closer
        else:
            out.append(ch)
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
    fits = lambda t: not too_long(dashes(t), sty)  # measured as displayed (closed dashes)
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
        t = open_dashes(t)
        for sep in (" — ", " – ", " | ", ": "):
            if sep in t:
                left = t.split(sep, 1)[0].strip()
                if len(left.split()) >= 4 and not contentless(left) and not fragment(left, t):
                    t = left
                    break
    if not fits(t):
        cuts = [m.start() for m in _PREP.finditer(t)] + [m.start() for m in re.finditer(r",\s", t)]
        for pos in sorted(cuts, reverse=True):  # smallest removal first
            cand = t[:pos].rstrip(" ,;:")
            if len(cand.split()) >= 6 and fits(cand) and not contentless(cand) and not fragment(cand, t):
                t = cand
                break
    t = t.rstrip(" ,;:")
    if t == title.strip():
        return title
    return clean(t, sty)[0] or title


STRONG_VERBS = {
    "is", "are", "was", "were", "be", "been", "isn't", "aren't", "wasn't", "has", "have", "had", "hasn't", "haven't",
    "do", "does", "did", "don't", "doesn't", "didn't", "can", "can't", "could", "would", "should", "must", "may",
    "might", "will", "won't", "says", "said", "say", "claims", "claimed", "calls", "called", "wants", "wanted",
    "gets", "got", "goes", "went", "makes", "made", "takes", "took", "puts", "put", "sets", "set", "comes", "came",
    "wins", "won", "loses", "lost", "blocks", "passes", "fires", "seizes", "slams", "exposes", "indicts", "rules",
    "orders", "bans", "kills", "hits", "sues", "warns", "vows", "backs", "rejects", "approves", "confirms",
    "denies", "faces", "leads", "led", "beats", "beat", "defies", "blasts", "deploys", "packs", "scraps", "gives",
    "gave", "fails", "fizzle", "fizzles", "grows", "grew", "burns", "burned", "admits", "demands", "rips", "torches",
    "launches", "joins", "invites", "honors", "turns", "probes", "stirs", "sends", "files", "drops", "pays",
    "know", "knows", "think", "thinks", "prefer", "prefers", "need", "needs", "keeps", "kept"}
_DANGLING = {"that", "which", "whose", "of", "the", "a", "an", "and", "or", "but", "than"}


_TIME_UNITS = {"days", "hours", "weeks", "months", "years", "minutes", "moments", "day", "hour", "week", "month", "year"}


def _toks(t):
    return [re.sub(r"[^a-z0-9%']", "", w.lower().replace("’", "'")) for w in open_dashes(t).split()]


def has_strong_verb(t):
    """A finite verb from the strong list, an -ed/-ing past/progressive after a name, or a passive 'Is/Are X-ed'.
    (Stricter than the bland detector: plural nouns like 'Attacks' do not count.)"""
    return any(w in STRONG_VERBS for w in _toks(t))


def fragment(display, original=None):
    """True when the display headline is not a complete thought (see incomplete())."""
    return incomplete(display, original) is not None


def _fragment_core(display, original=None):
    """True when a display headline reads as a cut-off fragment: it ends on a dangling function word,
    it dropped every strong verb the original had ('‘Vast Majority’ of Iran’s Attempted Attacks' from
    '... Attacks on Hormuz Are Unsuccessful, CENTCOM Says'), or it stops a 'that/which/who' clause before
    its verb ('Racist Claim That Arab Mothers')."""
    toks = [w for w in _toks(display) if w]
    if not toks:
        return False
    if toks[-1] in _DANGLING:
        return True
    if original is not None:
        left = [w for w in _toks(re.split(r"\s*—\s*|\s[–|]\s|:\s", original)[0]) if w]
        whole_left = left and toks[-1] == left[-1] and len(toks) >= len(left) - 2  # a dash/colon tail was dropped
        if has_strong_verb(original) and not has_strong_verb(display) and not whole_left:
            return True
        otoks = [w for w in _toks(original) if w]
        if toks[-1] in _TIME_UNITS:
            k = len(toks)
            nxt = next((otoks[j + k] for j in range(len(otoks) - k) if otoks[j:j + k] == toks), None)
            if nxt in ("after", "before", "ago", "later", "earlier", "since"):
                return True  # 'Rally Comes Days' cut from 'Rally Comes Days After Terror Plot Foiled'
        for i, w in enumerate(toks):
            if w in ("that", "which", "who") and 0 < i and len(toks) - i - 1 <= 3 \
                    and not any(x in STRONG_VERBS or x.endswith("ed") for x in toks[i + 1:]) and len(otoks) > len(toks):
                return True
    return False


_MORE_VERBS = set("""
accuse accuses accused add adds added admit admitted announce announces announced arrest arrests ask asks asked
attack attacks attacked become becomes became begin begins began blame blames blamed break breaks broke bring brings brought
build builds built buy buys bought catch catches caught charge charges charged claim cut cuts dies died drop dropped
end ends ended expose fall falls fell feel feels felt find finds found flee flees fled fly flies flew force forces forced
get give go goes gone hand hands handed help helps helped hide hides hid hold holds held keep kill lead leave leaves left
let lets lie lies lied look looks looked lose meet meets met move moves moved pay plan plans planned push pushes pushed
quit quits raise raises raised reveal reveals revealed run runs ran see sees saw seen seek seeks sought sell sells sold
send sent show shows showed shown sit sits sat speak speaks spoke spend spends spent stand stands stood start starts started
stop stops stopped take tell tells told threaten threatens threatened try tries tried win wins write writes wrote
threw throw throws shot shoot shoots tied tie ties hit struck strike strikes slain slay sank sink rose rise rises
hung hang swore swear beaten beat thrown stolen steal steals stole fought fight fights sought wrote written drew
draw draws grew grow shut shuts quit spread spreads led bit bite bites bought rode rides ride drove drive drives
promise promises deliver delivers make slam probe seize seizes back reject warn vow sue ban block fire hit eye eyes
eyed weigh weighs mull mulls urge urges push pull pulls rip rips torch rally rallies erupt erupts surge surges soar
soars plunge plunges sink sinks fear fears sparks spark ignite ignites target targets mock mocks defend defends
shall believe believes care cares differ differs hire hires hurt hurts help kill killing fail cost costs win lose love hate hates want need serve serves
""".split())
_DET = {"the", "a", "an", "of", "his", "her", "their", "its", "our", "my", "your", "this", "that", "these", "those",
       "for", "in", "on", "at", "by", "with", "from", "into", "over", "about", "and", "or", "new", "top", "big"}
_NOT_VERB_S = {"news", "times", "politics", "affairs", "us", "u.s", "dems", "democrats", "republicans", "americans",
              "states", "texas", "kansas", "illinois", "arkansas", "paris", "chaos", "crisis", "isis", "status",
              "series", "species", "jews", "christians", "kids", "parents", "voters", "officials", "students",
              "police", "troops", "rights", "lives", "jobs", "taxes", "prices", "sales", "rates", "ties", "this",
              "his", "its", "has", "was", "is", "as", "yes", "thanks", "less", "ess", "boss", "class", "press",
              "business", "congress", "progress", "witness", "access", "process", "glass", "mass", "loss",
              "illness", "fitness", "madness", "weakness", "kindness", "darkness", "sickness"}



def _vtoks(t):
    return [re.sub(r"[^a-z0-9'.-]", "", w.lower().replace("’", "'").replace("‘", "'")).strip(".'") for w in t.split()]



_PREPS = {"before", "after", "while", "without", "against", "toward", "towards", "across", "through", "beyond",
          "via", "per", "like", "than", "amid", "during", "since", "until", "upon", "within", "behind", "under"}
_PLURAL_SUBJ = {"media", "gop", "police", "people", "dems", "democrats", "republicans", "feds", "justices", "voters",
                "officials", "parents", "students", "critics", "experts", "leaders", "lawmakers", "democrats", "americans"}
_ADVERBS = {"still", "also", "now", "never", "finally", "quietly", "again", "even", "just", "already", "reportedly"}


def finite_verb(t):
    """Heuristic finite-verb test for title-case headlines (no tagger available in the build)."""
    raw = [w for w in open_dashes(t).split() if _vtoks(w) and _vtoks(w)[0]]
    ws = [_vtoks(w)[0] for w in raw]
    poss = [bool(re.search(r"(?:s[’']|[’']s)[^A-Za-z]*$", w)) for w in raw]  # Dems’ / Iran’s
    for i, w in enumerate(ws):
        prev = ws[i - 1] if i else ""
        prev_poss = poss[i - 1] if i else False
        if i and not prev_poss and prev not in _DET and prev not in _PREPS:
            plural_prev = (prev.endswith("s") and not prev.endswith(("ss", "us", "is")) and prev not in _NOT_VERB_S - _PLURAL_SUBJ) \
                or prev in _PLURAL_SUBJ or (prev in _ADVERBS and i >= 2) or (i >= 2 and ws[i - 2] == "and")
            if plural_prev and len(w) > 2 and w not in _DET and w not in _PREPS and not w.endswith(("s", "ed", "ing", "ly")) \
                    and not w[0].isdigit() and i + 1 < len(ws):
                return True  # base-form verb after a plural subject: 'Dems Approach a', 'Media Skip', 'Justices Grant 3'
            if len(w) > 5 and w.endswith("ing") and w not in ("morning", "evening", "building", "thing", "spring", "string") \
                    and not raw[i - 1].endswith(","):  # 'Persistent, Disturbing Rise' is an adjective list
                return True  # predicate progressive: 'Pain-Gain Formula Working Against Trump'
        prev = "" if prev_poss and not prev.endswith("'s") else prev
        if re.search(r"'(?:re|m|ve|ll|d)$", w) or w in ("it's", "he's", "she's", "that's", "there's", "what's", "who's", "here's"):
            return True  # 'You're Losing', 'It's Over'
        if prev in ("i", "you", "we", "they", "he", "she", "it", "who") and w not in _DET:
            return True  # pronoun subject: the next word is its verb ('I Believe', 'You Rule')
        if len(w) > 5 and w.endswith("ing") and prev.endswith("ly"):
            return True  # 'Trump Reportedly Reconsidering ...'
        if any(p in STRONG_VERBS or p in _MORE_VERBS for p in w.split("-")[1:]):
            return True  # 'Co-Wrote', 'Re-Elected'
        if w in STRONG_VERBS or w in _MORE_VERBS:
            aux = w in _AUXV
            if not aux and (prev in _DET or prev.endswith("'s") or (prev.endswith(("ing", "ed")) and len(prev) > 5)):
                continue  # 'Disturbing Rise', 'Iran's Attacks', 'Attempted Attacks', 'the Fall'
            return True
        if prev == "to" and i >= 2 and len(w) > 2 and w not in _DET:
            return True  # 'Trump to Sign Bill' (headline future)
        if len(w) > 4 and w.endswith("ed") and prev not in _DET and not prev.endswith("'s"):
            return True  # 'Ex-Coach Arrested', 'Fires Raged'
        if len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "'s", "us", "is")) and w not in _NOT_VERB_S \
                and i > 0 and prev not in _DET and not prev.endswith("'s") and not prev.endswith("ed") and not prev.isdigit():
            return True  # 'Trump Signs', 'Iran Fires'
    return False

_AUXV = {"is", "are", "was", "were", "has", "have", "had", "will", "won't", "can", "can't", "could", "would",
         "should", "must", "may", "might", "do", "does", "did", "don't", "doesn't", "didn't", "isn't", "aren't",
         "wasn't", "hasn't", "haven't", "says", "said", "shall"}


def missing_verb(t):
    """No finite verb anywhere: a noun phrase ('Socialism's Persistent, Disturbing Rise'). Accepted
    headline-ese counts as a verb: a predicate participle ('Ex-Coach Arrested', 'Dad Tied to ...'), the
    headline future ('Trump to Sign'), a progressive after an adverb, and labeled / speaker-colon forms
    ('Homan: ...', 'WSJ: ...'), or a quoted line with its own verb."""
    t = t.strip()
    if re.match(r"^[^:]{2,30}:\s", t):  # 'Homan: ...', 'WSJ: ...'
        return False
    if re.search(r"[‘“].{6,}[’”]", t) and finite_verb(re.sub(r".*?[‘“](.*?)[’”].*", r"\1", t)):
        return False
    return not finite_verb(t)


_COMPLEMENT_VERBS = {"put", "puts", "putting", "placed", "placing"}
_PARTICLES = {"on", "in", "under", "at", "to", "into", "onto", "behind", "back", "up", "off", "out", "down", "away",
              "aside", "before", "over", "through", "forward", "atop", "inside", "outside", "near", "beside", "beyond", "above", "below", "ahead", "first", "last"}
_WH = {"why", "how", "what", "when", "where", "who"}


def missing_complement(t):
    """'Why Obama Admin Put Abdul El-Sayed's Sister-in-Law' (from '... on Terror Watch List'): a verb
    that needs a place or second object ('put', 'placed') with nothing after it to say where."""
    ws = [w for w in _toks(t) if w]
    idx = [i for i, w in enumerate(ws) if w in _COMPLEMENT_VERBS]
    return bool(idx) and not any(w in _PARTICLES for w in ws[idx[-1] + 1:])


def incomplete(display, original=None):
    """Why a displayed headline is not a complete thought, or None. Checked on every displayed headline
    (source, shortened, override): dangling or cut-off endings (fragment rules below), no finite verb,
    a verb missing its required complement, or an explainer ('Why ...', 'How ...') cut short."""
    if _fragment_core(display, original):
        return "cut_off"
    if missing_verb(display):
        return "no_finite_verb"
    if missing_complement(display):
        return "missing_complement"
    ws = [w for w in _toks(display) if w]
    for i, w in enumerate(ws):  # 'Racist Claim That Arab Mothers': a relative clause that never gets its verb
        rest = ws[i + 1:]
        if w in ("that", "which") and 0 < i and 0 < len(rest) <= 2 and not rest[0].endswith("ly") \
                and rest[0].strip("'") not in ("way", "time", "much", "many", "far", "long", "day", "point", "one", "kind") \
                and not any(x in STRONG_VERBS or x in _MORE_VERBS or x.endswith("ed") for x in rest):
            return "cut_off"
    if original is not None:
        ws, os_ = [w for w in _toks(display) if w], [w for w in _toks(original) if w]
        main = [w for w in _toks(re.split(r"\s*—\s*|\s[–|]\s|:\s", original)[0]) if w]
        if ws and ws[0] in _WH and len(ws) < len(main) and os_[:len(ws)] == ws:
            return "cut_explainer"  # an explainer question needs its whole predicate
    return None


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


def _slug_words(url):
    import urllib.parse
    seg = [x for x in urllib.parse.urlparse(url or "").path.split("/") if x]
    seg = [x for x in seg if not re.fullmatch(r"[\d.]+|n?\d{5,}|index\.html?", x)]
    last = re.sub(r"\.(html?|php|aspx?)$", "", seg[-1]) if seg else ""
    return [w for w in re.split(r"[-_]+", last.lower()) if w and not re.fullmatch(r"n?\d{5,}", w)]


def truncated(title, url="", vocab=None):
    vocab = vocab if vocab is not None else VOCAB
    """True if a source title looks cut off: ends with an ellipsis, ends mid-word (dangling hyphen
    or apostrophe), or its last word is a strict prefix of a word in the URL slug, or the slug's
    last word itself is cut off at the same point (e.g. "...Fraud Investigatio" / "...-investigatio/")."""
    t = (title or "").strip()
    if not t:
        return False
    if t.endswith(("…", "-", "–")) or (t.endswith("...") and not re.search(r"['‘’\"“”]\s*$|\.\.\.['’\"”]$", t)):
        return True
    if re.search(r"['‘’\"“”)]$", t):  # ends with a closing quote: a whole quoted phrase
        return False
    last = re.sub(r"[^a-z0-9]", "", t.split()[-1].lower())
    if len(last) < 3:
        return False
    slug = _slug_words(url)
    if slug and slug[-1] != last and slug[-1].startswith(last) and t.split()[-1].lower().strip("’'\"") != slug[-1] \
            and len(slug[-1]) > len(last) + 1 and last in [re.sub(r"[^a-z0-9]", "", x.lower()) for x in t.split()[-1:]]:
        return True  # slug finishes the title's last word ("...Immigra" / "-immigration")
    prev = re.sub(r"[^a-z0-9]", "", t.split()[-2].lower()) if len(t.split()) > 1 else ""
    if prev and any(slug[i] == prev and slug[i + 1] != last and slug[i + 1].startswith(last)
                    and len(slug[i + 1]) > len(last) + 1 for i in range(len(slug) - 1)):
        return True  # same, mid-slug: "...Votes on Immigra" / "votes-on-immigration-bill"
    # cut-off word: rare in today's headlines while a longer word starting with it is common
    # ("Investigatio" vs "Investigation"); vocab = word counts across all of today's titles
    # slug cut at the same point: a word that never appears in today's titles or descriptions except
    # here, while a 1-2 letter longer completion is common ("investigatio" / "investigation")
    if vocab and slug and slug[-1] == last and len(last) >= 6 and vocab.get(last, 0) <= 1 and any(
            w.startswith(last) and 0 < len(w) - len(last) <= 2 and n >= 3 for w, n in vocab.items()):
        return True
    return False


def repair_truncated(title, url="", vocab=None):
    """Complete a cut-off last word from the URL slug (or the most common completion in today's
    headlines); drop a trailing ellipsis if the rest is whole words. Returns None if no repair."""
    t = re.sub(r"\s*(…|\.\.\.)$", "", (title or "").strip())
    words = t.split()
    if not words:
        return None
    last = re.sub(r"[^a-z0-9]", "", words[-1].lower())
    sl = _slug_words(url)
    full = sl[-1] if sl and sl[-1] != last and sl[-1].startswith(last) and len(last) >= 3 else None
    prev = re.sub(r"[^a-z0-9]", "", words[-2].lower()) if len(words) > 1 else ""
    if not full and prev:
        full = next((sl[i + 1] for i in range(len(sl) - 1) if sl[i] == prev and sl[i + 1] != last
                     and sl[i + 1].startswith(last) and len(last) >= 3), None)
    if not full and vocab:
        cands = [(n, w) for w, n in vocab.items() if w.startswith(last) and 0 < len(w) - len(last) <= 2 and n >= 3]
        full = max(cands)[1] if cands else None
    if full:
        words[-1] = full.capitalize() if words[-1][:1].isupper() else full
        return " ".join(words)
    if t != (title or "").strip() and len(words) >= 5:  # ellipsis dropped, rest is whole words
        return t
    return None


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


_ABBREV = {"mr", "mrs", "ms", "dr", "st", "sr", "jr", "gov", "sen", "rep", "gen", "lt", "col", "sgt", "capt",
           "prof", "rev", "vs", "v", "no", "inc", "co", "corp", "ltd", "dept", "ft", "mt", "jan", "feb", "aug",
           "sept", "sep", "oct", "nov", "dec", "pres", "atty", "supt", "approx", "etc", "sec", "wis", "calif",
           "ariz", "mich", "minn", "fla", "ill", "mass", "conn", "tenn", "wash", "colo", "okla", "penn"}


def _sentence_end(prev):
    """True if token `prev` ends a sentence (. ? ! possibly followed by closing quotes/brackets), so the
    next word starts a new sentence. Ellipsis dots (". . .", "...", "…") and abbreviations (U.S., D.C.,
    Mr., Gov.) do not count."""
    if prev[-1:] in ("\"", "'", "’", "”"):
        return False  # punctuation inside a closing quote is embedded: Asked ‘Why?’ and Walked Out
    t = prev.rstrip(")]")
    if not t or t[-1] not in ".?!":
        return False
    if t[-1] in "?!":
        return True
    if t.endswith("..") or set(t) <= {"."}:
        return False
    core = t.rstrip(".").lstrip("\"'‘“([")
    if re.fullmatch(r"(?:[A-Za-z]\.)+[A-Za-z]?", core + ".") or re.fullmatch(r"[A-Za-z]", core):
        return False  # U.S., D.C., initials
    return core.lower() not in _ABBREV


def lowercase_small_words(title, sty=None):
    """Lowercase Title-Case short prepositions/articles (In, Of, To, On, At, For, A, The) except
    as the first word or right after ':', '|', a sentence end or an opening quote (a dash is not a break). All-caps tokens are left alone,
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
        if toks[i - 1][-1:] in (":", "|", "‘", "“", "'", '"') or toks[i - 1] == "-" \
                or _sentence_end(toks[i - 1]):
            continue
        if w == "A" and (i + 1 >= len(toks) or not toks[i + 1][:1].isalnum()):
            continue
        toks[i] = w.lower()
    return " ".join(toks)


HYPHEN_SMALL = {"a", "an", "the", "and", "but", "or", "nor", "as", "at", "by", "for", "in", "of", "on", "to", "vs", "per", "via"}


def hyphen_case(core, cfg=None):
    """Chicago-style hyphenated compounds: capitalize every element (Fast-Moving, 18-Year-Old, Anti-Trump)
    except articles, prepositions and conjunctions in the middle (Soft-on-Crime, Up-to-Date, Mother-in-Law).
    Elements with capitals beyond the first letter (SJSU, McCarthy, iPhone, COVID) are kept as written."""
    small = set((cfg or {}).get("hyphen_small_words") or HYPHEN_SMALL)
    ps = core.split("-")
    out = []
    for i, p in enumerate(ps):
        if not p or not p[0].isalpha() or (p[1:] != p[1:].lower()) or (p[0].islower() and p[1:] != p[1:].lower()):
            out.append(p); continue
        if 0 < i < len(ps) - 1 and p.lower() in small:
            out.append(p.lower()); continue
        out.append(p[:1].upper() + p[1:])
    return "-".join(out)


def title_case(title, sty=None):
    """AP/Chicago-style title case. Lowercase small words (a, an, the, and, but, or, nor, as, at,
    by, for, if, in, of, on, to, vs, with, from, into, onto, upon) except first/last word or after ':', '|', a
    sentence end or an opening quote (not after a dash: 'Shows—and Leaves Unanswered'); capitalize every other lowercase word (incl. hyphen parts). Never lowercases
    words with internal capitals (acronyms, McDonald, iPhone) and keeps lowercase name particles
    before a capitalized name ('el Sayed'). 'Up' stays capitalized (phrasal particles: 'Take Up').
    'over' is lowercased as a preposition ('Feud over Rule') but capitalized as an adverb/particle
    ('Takes Over', 'Hands Over Files', 'Game Over'); see particle_prepositions."""
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
        if core and core[0].isdigit() and "-" in core.strip("-") and w not in keep and core not in keep:
            out.append(lead + hyphen_case(core, cfg) + trail); continue  # 18-Year-Old, 2-to-1
        if not core or not core[0].isalpha() or w in keep or core in keep:
            out.append(w); continue
        prev = toks[i - 1] if i else ""
        # a dash is not a boundary (Chicago): minor words after it stay lowercase ('Shows—and Leaves')
        boundary = i == 0 or i == n - 1 or prev[-1:] in (":", "|") or prev == "-" \
            or _sentence_end(prev) or lead[-1:] in ("‘", "“", "(", "[")
        low = core.lower()
        pp = cfg.get("particle_prepositions") or {}
        if not boundary and low in pp and low != "_comment" and (core == low or core == core.capitalize()):
            nxt = toks[i + 1] if i + 1 < n else ""
            particle = prev.lower().strip("‘’“”'\"") in {v.lower() for v in pp[low]} or trail or not nxt[:1].isalnum() and nxt[:1] not in ("‘", "“", "$")
            out.append(lead + (core.capitalize() if particle else low) + trail); continue
        if not boundary and low in small and (core == low or core == core.capitalize()):
            out.append(lead + low + trail); continue
        if low in parts_ and core == low and i + 1 < n and toks[i + 1][:1].isupper():
            out.append(w); continue  # el Sayed, bin Salman
        if low == "to" and not (i == 0 or prev[-1:] == ":" or _sentence_end(prev) or lead[-1:] in ("‘", "“")):
            out.append(lead + low + trail); continue  # always lowercase 'to', incl. infinitives and last word
        if "-" in core.strip("-"):
            out.append(lead + hyphen_case(core, cfg) + trail); continue
        if core != low:  # has capitals already (Title, ACRONYM, McDonald, iPhone): keep
            out.append(w); continue
        out.append(lead + core[:1].upper() + core[1:] + trail)
    return " ".join(out)


VOCAB = {}  # today's word counts, set by the build


def vocabulary(titles):
    v = {}
    for t in titles:
        for w in re.findall(r"[a-z0-9]+", (t or "").lower().replace("’", "'")):
            v[w] = v.get(w, 0) + 1
    return v
