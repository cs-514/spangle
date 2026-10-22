"""Quote-of-the-Day headline validator. A QOTD headline must be a complete, standalone thought: a subject plus
a verb ("Pride Only Wants More Than the Next Man"), a crisp imperative ("Know the Enemy and Know Yourself"), or a
question ("Where Shall the Power to Tax Stop?"). Never a noun phrase ("The Inherent Right of Self-Defense") or a
subordinate clause that trails off ("How Politics Curdled Equality into Resentment"). Short: at most 8 words and
50 characters (aim for 3-7), a framing or thesis that sets the quote up; never the quote's punchline or its
opening copied out (the reader gets the payoff in the quote itself). House style: title case
(with/to/over lowercase), single curly quotes. Reuses the news fragment detector for dangling endings."""
import re
from . import headline as h

MAX_WORDS = 8   # a short framing (aim for 3-7 words), not the quote's opening copied out
MAX_CHARS = 50
SPOIL_SHARE = 0.6  # share of the headline's content words found in the quote's closing / punchiest line
SUBORDINATE = {"how", "why", "what", "when", "where", "which", "who", "whose", "that", "because", "if", "while",
               "although", "though", "whether"}
# Finite / imperative verbs common in quote headlines (in addition to headline.STRONG_VERBS).
VERBS = set("""
am be is are was were been being has have had do does did shall will would should can could may might must
attack attacks avoid avoids bear bears beware blame blames breed breeds bring brings brought build builds built
call calls care cares carry carries cease ceases cherish come comes cost costs cultivate dare dares delivers deliver
destroy destroys die dies died differ disdains disdain drink eat ends endure enlightened explain expect expects
face faces fall falls fear fears feel feels fight fights find finds finish flee flourish flourishes follow follows
foil forced forget forgives forgive frees free gained get gets give gives go goes grant grants grow grows guarantee
guarantees hate hates hides hide invent invents invites invite keep keeps knits know knows laugh lay lead leads led
leave leaves let lift lifts live lives look looks lose loses make makes march mean means move moves need needs
observe offer offers pays pay perish prefer prefers prevail prospers prosper put puts reach reaches read reads
remember rest rests rewrite rob robs rouse rule rules say says see sees seek seeks serve serves settle shame
smile speak stand stands stop stops strive study studies swear take takes taken teach tear thrive think tighten
trade treat turned turn turns use uses want wants weigh weighs win wins worsened wrote written
encourage exclude detest believe believes eyes mislead misleads ended asserted begins belongs evaporates limits
spread threaten threatens return returns emanates benefits benefit insists sought rises fails stands marches
describes misses sharpens draws depend ignores upended questions skip shaped sounds erodes challenges meant
learn settled drew announce accuses names ties hold lays placed diagnoses defines issues sustains frames champions
begin survive mourns refuse backed finds rejects tests dissects recalls inherit accepts craves outlast predicts bets explains check treats prizes matters decides favors meet exist
answers refuses defends scorns restores steadies owns chooses condemns rallies rebukes longs mocks backfire settles
""".split())
AMBIGUOUS = {"called"}  # participles that usually modify a noun ('This Breed Called Americans')
REL = {"what", "that", "which", "who", "whom", "whose", "when", "where", "how", "why"}  # 'to' is an infinitive, not a clause
NOT_VERBS = {"news", "times", "politics", "affairs", "arms", "means", "lovers", "kings", "fathers", "warfare"}


def _toks(t):
    return [re.sub(r"[^a-z']", "", w.lower().replace("’", "'")) for w in h.open_dashes(t).split()]


def has_verb(t):
    """A main-clause verb: verbs after 'to' (infinitives) or inside a relative/subordinate clause don't count
    ('Duty to Say What the Law Is', 'Power to Tax, Power to Destroy')."""
    toks = [w for w in _toks(t) if w]
    for i, w in enumerate(toks):
        if i > 0 and toks[i - 1] == "to":
            continue  # infinitive: not a main-clause verb ('Duty to Say')
        if i > 0 and w in REL:
            # subject relative clause ('Judges Who Look Outside … See Only Themselves', 'Those Who Flee Find …'):
            # its own verb comes first; a second verb after it is the main verb
            rest = [x for x in toks[i + 1:] if x in VERBS or x in h.STRONG_VERBS]
            return w in ("who", "that", "which") and len(rest) >= 2
        base = w[:-2] if w.endswith("'s") else w
        if w in AMBIGUOUS:
            continue
        if w in VERBS or w in h.STRONG_VERBS or base in VERBS:
            return True
        if w.endswith(("n't", "'ll", "'re", "'ve", "'d", "'m")):
            return True
        if w.endswith("'s") and i == 0 and w in ("it's", "that's", "there's", "here's", "what's", "he's", "she's"):
            return True
    return False


_STOP = set("""a an the and or but nor so yet of to in on at by for with from into over as is are was were be been
it its this that these those than then there their they them he she his her him we our us you your i my me not no
do does did will would shall should can could may might must have has had what which who whom when where how why
all any each every some such only own just very more most much many""".split())


def _content(t):
    return {w[:5] for w in re.findall(r"[a-z]+", (t or "").lower().replace("’", "'")) if w not in _STOP and len(w) > 2}


def _sentences(q):
    return [x for x in re.split(r"(?<=[.!?])[’”\"']?\s+", (q or "").strip()) if x.strip()]


def spoils(headline, quote):
    """The headline gives away the payoff: most of its content words come from the quote's closing sentence
    or its punchiest short line (a sentence of 12 words or fewer). The headline should frame the quote
    ('Power Grabs Rarely Announce Themselves'), not repeat its best line ('This Wolf Comes as a Wolf')."""
    hw = _content(headline)
    if not hw or not quote:
        return False
    sents = _sentences(quote)
    lines = sents[-1:] + [x for x in sents[:-1] if len(x.split()) <= 12]
    for line in lines:
        shared = hw & _content(line)
        if len(shared) >= 2 and len(shared) / len(hw) >= SPOIL_SHARE:
            return True
    return False


def problems(headline, sty=None, quote=None):
    """List of reasons the headline fails (empty = OK). With the quote, also rejects a headline that repeats
    the quote's closing or punchiest line (it must set the quote up, not spoil it)."""
    t = (headline or "").strip()
    out = []
    if not t:
        return ["empty"]
    words = h.open_dashes(t).split()
    if len(words) > MAX_WORDS or len(t) > MAX_CHARS:
        out.append(f"too long ({len(words)} words, {len(t)} chars; max {MAX_WORDS}/{MAX_CHARS})")
    if any(c in t for c in '"“”'):
        out.append("double quotes (use single curly ‘…’)")
    if "'" in t:
        out.append("straight apostrophe or quote (use ’ and ‘…’)")
    if h.dashes(t) != t:
        out.append("dash style (use a closed em dash: ‘Word—Word’, never ‘ -- ’ or ‘ — ’)")
    if t.endswith(("…", "...", ",", ";", ":", "—", "–", "-")):
        out.append("trails off")
    first = _toks(t)[0] if _toks(t) else ""
    main = t
    if first in SUBORDINATE and not t.endswith("?"):
        rest = t.split(",", 1)[1] if "," in t else ""
        if not rest.strip() or not has_verb(rest):
            out.append(f"starts a subordinate clause ('{words[0]}') without completing it")
        main = rest or t
    if not t.endswith("?") and not has_verb(main) and not any(has_verb(p) for p in re.split(r"[,;:]", main)):
        out.append("no verb: a noun phrase, not a complete thought")
    if h._fragment_core(t):
        out.append("ends on a dangling word")
    if quote and spoils(t, quote):
        out.append("repeats the quote's punchline (frame or set up the quote; let the quote deliver its best line)")
    tc = h.title_case(t, sty)
    if tc != t:
        out.append(f"not house title case (expected: {tc})")
    return out


def ok(headline, sty=None, quote=None):
    return not problems(headline, sty, quote)
