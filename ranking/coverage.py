"""Cross-outlet coverage: clustering lives in cluster(); score = distinct outlets."""
import math, re
from .util import tokens, saturate
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
    for i, c in enumerate(clusters):
        c["id"] = i
    for c in clusters:
        c["outlets"] = {_outlet(s) for s in c["items"]}
        dated = [s["when"] for s in c["items"] if s["when"]]
        c["newest"] = max(dated) if dated else None
    return clusters


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
