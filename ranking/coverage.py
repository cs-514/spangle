"""Cross-outlet coverage: clustering lives in cluster(); score = distinct outlets."""
import math, re
from .util import tokens, saturate, STOP
NAME = "coverage"

def _outlet(s):
    return s["source"].replace(" Politics", "").replace(" Opinion", "")

def cluster(stories, threshold, max_entity_df=25):
    """IDF-weighted greedy clustering: rare shared terms (names, places) count most."""
    toks = [set(tokens(s["title"]) + tokens(s["desc"][:200])[:8]) for s in stories]
    df = {}
    for t in toks:
        for w in t:
            df[w] = df.get(w, 0) + 1
    n = len(stories) or 1
    idf = {w: math.log(n / c) for w, c in df.items()}
    clusters = []
    for s, tk in zip(stories, toks):
        tt = set(tokens(s["title"]))
        best, bs = None, 0.0
        for c in clusters:
            inter = tt & c["first"]  # compare to the founding headline to avoid chaining
            if len(inter) < 2:
                continue
            w_i = sum(idf[w] for w in inter)
            sim = w_i / (min(sum(idf[w] for w in tt), sum(idf[w] for w in c["first"])) or 1)
            if sim > bs:
                best, bs = c, sim
        if best is not None and bs >= threshold:
            best["items"].append(s); best["title_tokens"] |= tt
        else:
            clusters.append({"id": len(clusters), "items": [s], "title_tokens": set(tt), "first": set(tt)})
    # second pass: merge clusters sharing a distinctive named entity (e.g. "Pope Leo")
    # plus at least one other rare headline term. Very common entities are ignored.
    ent_df = {}
    for s in stories:
        for e in entities(s["title"]):
            ent_df[e] = ent_df.get(e, 0) + 1
    for c in clusters:
        # entities of the founding headline only, so merges can't chain across loosely related stories
        c["ents"] = {e for e in entities(c["items"][0]["title"]) if ent_df.get(e, 0) <= max_entity_df}
    rare = lambda c: {w for w in c["title_tokens"] if idf.get(w, 0) >= math.log(n / 6)}
    merged = True
    while merged:
        merged = False
        for i, a in enumerate(clusters):
            for b in clusters[i + 1:]:
                shared = a["ents"] & b["ents"]
                if shared:
                    ent_words = {w for e in shared for w in e.split()}
                    if len((rare(a) & rare(b)) - ent_words) >= 1:
                        a["items"] += b["items"]; a["title_tokens"] |= b["title_tokens"]
                        clusters.remove(b); merged = True
                        break
            if merged:
                break
    clusters = event_merge(clusters, stories)
    for i, c in enumerate(clusters):
        c["id"] = i
    for c in clusters:
        c["outlets"] = {_outlet(s) for s in c["items"]}
        dated = [s["when"] for s in c["items"] if s["when"]]
        c["newest"] = max(dated) if dated else None
    return clusters


# Event vocabulary: different words for the same development count as one shared term.
SYN = {"probe": "inves", "probi": "inves", "subpo": "inves", "raid": "inves", "raids": "inves", "raide": "inves",
       "inqui": "inves", "lives": "lives", "live-": "lives", "seize": "inves", "seizu": "inves", "seiza": "inves", "passp": "inves",
       "mail": "lette", "maile": "lette", "envel": "lette", "packa": "lette",
       "sue": "lawsu", "sues": "lawsu", "sued": "lawsu", "suing": "lawsu",
       "indic": "charg", "arres": "charg", "convi": "charg",
       "killi": "murde", "kille": "murde", "kills": "murde", "slain": "murde", "slayi": "murde"}
GENERIC = {"repor", "says", "trump", "presi", "news", "state", "house", "democ", "repub", "polit", "biden",
           "white", "watch", "video", "breaking", "exclu", "opini", "ameri", "gover", "feder", "offic"}


def stems(title):
    out = set()
    for w in tokens(title.replace("’", "'")):
        w = re.sub(r"'s$", "", w).strip("'")
        if len(w) < 3:
            continue
        st = w[:5]
        out.add(SYN.get(st, SYN.get(w, st)))
    return out


INSTITUTION = {"court", "house", "department", "service", "party", "news", "state", "states", "city", "county",
               "university", "committee", "senate", "congress", "times", "post", "journal", "network", "bureau",
               "school", "today", "history", "promo", "code", "bonus", "sportsbook", "new", "york", "north", "south",
               "social", "security", "second", "first", "amendment", "national", "united", "american", "america",
               "fox", "breaking", "watch", "exclusive", "report", "opinion"}


def event_merge(clusters, stories, person_df=25, event_df=20, min_idf=2.85):
    """Third pass: one story per real-world event, even when outlets word it differently.
    A cluster joins an earlier "head" cluster when, comparing founding headlines only (first 3 items
    of each, never the merged union, so merges cannot chain):
      (a) they share a person-like name entity (two capitalized non-function words, not an institution
          or generic topic) seen in <= person_df headlines, or one side names that person by surname only, or
      (b) they share at least 3 event terms (each in <= event_df headlines) whose summed IDF reaches
          min_idf x log(corpus size) (so rare words like "powder" count far more than common ones), with synonyms folded
          (probe/subpoena/raid -> investigation, mail/envelope -> letter, sue -> lawsuit, killing/slain -> murder).
          Event terms are stems of 4+ letters, or a 3-letter acronym written in capitals (ICE, FBI)."""
    sdf, edf = {}, {}
    n = len(stories) or 1
    # 3-letter agency acronyms (ICE, FBI, DOJ) are event terms too, when written in capitals
    acr = {w.lower() for s in stories for w in re.findall(r"\b[A-Z]{3}\b", s["title"])} - GENERIC
    term = lambda w: len(w) >= 4 or w in acr
    # Proper names: words capitalized mid-headline in sentence-case headlines (title-case noise excluded)
    proper = set()
    for s in stories:
        ws = s["title"].replace("’", "'").split()
        if len(ws) >= 4 and sum(1 for w in ws[1:] if w[:1].islower()) >= len(ws[1:]) / 2:
            proper |= {re.sub(r"'s$|[^a-z'-]", "", w.lower()) for w in ws[1:] if w[:1].isupper()}
    for s in stories:
        for w in stems(s["title"]):
            sdf[w] = sdf.get(w, 0) + 1
        for e in entities(s["title"]):
            edf[e] = edf.get(e, 0) + 1

    def sig(c):
        heads = [x["title"] for x in c["items"][:3]]
        st = set().union(*(stems(h) for h in heads)) - GENERIC
        en = set().union(*(entities(h) for h in heads))
        persons = {e for e in en if 1 < edf.get(e, 0) <= person_df and not (set(e.split()) & (INSTITUTION | STOP))
                   and all(w in proper for w in e.split())}
        words = set().union(*(set(re.findall(r"[a-z][a-z'-]+", h.lower().replace("’", "'").replace("'s", ""))) for h in heads))
        named = {e for e in en if not (set(e.split()) & STOP) and all(w in proper for w in e.split())}
        return st, persons, (words, named)

    def match(a, b, people=True):
        (ra, pa, (wa, na)), (rb, pb, (wb, nb)) = a, b
        if not people:
            pa = pb = set()
        if pa & pb:  # same (non-ubiquitous) person: one ongoing story
            return True
        # surname-only mention ("the Omar probe") of a rare person named in full on the other side
        last = lambda ps: {e.split()[-1] for e in ps if len(e.split()[-1]) >= 4 and sdf.get(e.split()[-1][:5], 99) <= person_df}
        if (not nb and last(pa) & wb) or (not na and last(pb) & wa):
            return True
        shared = ra & rb
        return (sum(1 for w in shared if sdf.get(w, 0) <= event_df and term(w)) >= 3
                and sum(math.log(n / sdf[w]) for w in shared if term(w)) >= min_idf * math.log(max(n, 3)))

    heads = []  # (cluster, [founding signatures of every cluster merged into it])
    for c in clusters:
        sg = sig(c)
        for h, sigs in heads:
            # people links only against the head's founding headlines; event links against any member
            if match(sg, sigs[0]) or any(match(sg, x, people=False) for x in sigs[1:]):
                h["items"] += c["items"]; h["title_tokens"] |= c["title_tokens"]; sigs.append(sg)
                break
        else:
            heads.append((c, [sg]))
    # heads that now match through a later-joined member are the same story too
    merged = True
    while merged:
        merged = False
        for i, (h, sa) in enumerate(heads):
            for j in range(i + 1, len(heads)):
                g, sb = heads[j]
                if match(sa[0], sb[0]) or any(match(a, b, people=False) for a in sa for b in sb):
                    h["items"] += g["items"]; h["title_tokens"] |= g["title_tokens"]; sa += sb
                    heads.pop(j); merged = True
                    break
            if merged:
                break
    return [h for h, _ in heads]


ENT = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)")


def entities(title):
    """Capitalized word bigrams, e.g. "Ilhan Omar", "Pope Leo" (title-case noise is filtered by df caps)."""
    out = set()
    for m in ENT.findall(title.replace("’s", "").replace("'s", "")):
        w = m.lower().split()
        out |= {f"{w[i]} {w[i + 1]}" for i in range(len(w) - 1)}
    return out


def compute(clusters, settings, ctx):
    sat = settings["coverage"]["saturation_outlets"]
    return {c["id"]: saturate(len(c["outlets"]) - 1, sat - 1) / 0.75 if len(c["outlets"]) > 1 else 0.0 for c in clusters}
