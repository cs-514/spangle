"""Framing signal: headline framing toward configured entities. Returns 1.0 for
neutral/favorable headlines and lower values when a negative term appears within
a few words of a configured entity. Private config key "framing":
{"entities": [...], "negative_terms": [...], "window_words": 6, "lead_exclude": true,
 "court": {"actors": [...], "actions": [...]},
 "subject_terms": [...], "subject_entities": [...], "top_exclude": true}.
subject_terms flag only when a subject_entity comes BEFORE the term ("X Faces Lawsuit").
Flagged clusters get c["lead_excluded"] when lead_exclude is set."""
import re
from . import private
NAME = "framing"


def _neg(title, ents, terms, win, court=None, subject_terms=(), subject_ents=()):
    words = re.findall(r"[a-z0-9'.-]+", title.lower())
    text = " ".join(words)
    has = lambda xs: any(re.search(r"\b" + re.escape(x), text) for x in xs)
    # Whole-headline rule: a court/legal actor + adverse ruling language + an entity anywhere.
    if court and has(ents) and has(court.get("actors", [])) and has(court.get("actions", [])):
        return True
    epos = [len(text[:m.start()].split()) for e in ents for m in re.finditer(r"\b" + re.escape(e) + r"\b", text)]
    tpos = [len(text[:m.start()].split()) for t in terms for m in re.finditer(r"\b" + re.escape(t), text)]
    if any(abs(a - b) <= win for a in epos for b in tpos):
        return True
    # GOP-negative where the entity is the subject: "<entity> Faces Lawsuit", "<entity> Accused of ..."
    if subject_terms:
        se = list(subject_ents)  # subject rule uses its own list, so "DOJ ... indicted" (a win) is not flagged
        spos = [len(text[:m.start()].split()) for e in se for m in re.finditer(r"\b" + re.escape(e) + r"\b", text)]
        stpos = [len(text[:m.start()].split()) for t in subject_terms for m in re.finditer(r"\b" + re.escape(t), text)]
        return any(0 < b - a <= 2 for a in spos for b in stpos)  # entity is the grammatical subject
    return False


def compute(clusters, settings, ctx):
    cfg = private.load(ctx).get("framing")
    if not cfg or not cfg.get("entities"):
        return None
    ents = [e.lower() for e in cfg["entities"]]
    terms = [t.lower() for t in cfg.get("negative_terms", [])]
    win = cfg.get("window_words", 6)
    out, flagged = {}, 0
    for c in clusters:
        st = [t.lower() for t in cfg.get("subject_terms", [])]
        se = [e.lower() for e in cfg.get("subject_entities", [])]
        neg = sum(_neg(s["title"].replace("’", "'"), ents, terms, win, cfg.get("court"), st, se) for s in c["items"]) / len(c["items"])
        out[c["id"]] = 1.0 - neg
        if neg > 0 and cfg.get("lead_exclude"):
            c["lead_excluded"] = True
        if neg > 0 and cfg.get("top_exclude"):
            c["top_excluded"] = True  # out of the lead/Top Stories, placed low in the columns
        flagged += neg > 0
    print(f"signal framing: {flagged} clusters flagged")
    return out
