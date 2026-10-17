"""Lead eligibility and lead scoring.

Public settings ("lead" in settings.json) hold generic defaults; the private config
(ALIGNMENT_CONFIG key "lead") may override any key. Keys:
  gate_paths / gate_categories / gate_keywords : hard topic gate (sports, lifestyle, ...)
  soft_gate_paths / soft_gate_categories      : softer gate for the top-stories block
  political_terms                              : marks a story as political/cultural
  win_terms, win_entities, opponent_loss_terms : "win" lexicon (term + entity, or opponent-loss phrase)
  outrage_terms, intensity_terms               : "outrage" lexicon and intensity boosters
  threshold                                    : minimum win/outrage signal for the lead
  weights                                      : {"signal", "coverage", "amplifiers", "alignment", "rank", "engagement", "consensus"}
  candidates                                   : how many top-ranked clusters to consider
"""
import re
from . import private


def config(settings, ctx):
    cfg = dict(settings.get("lead", {}))
    cfg.update(private.load(ctx).get("lead", {}))
    return cfg


def _has(text, terms):
    return sum(1 for t in terms if re.search(r"(?<![a-z])" + re.escape(t.lower()), text))


def _fields(s):
    return s["title"].lower(), (s.get("cats") or "").lower(), s["link"].lower()


def gated(s, cfg, soft=False):
    """True if the story is excluded by the topic gate."""
    title, cats, link = _fields(s)
    paths = cfg.get("soft_gate_paths" if soft else "gate_paths", [])
    catsx = cfg.get("soft_gate_categories" if soft else "gate_categories", [])
    if any(p.lower() in link for p in paths):
        return True
    if any(re.search(r"(?<![a-z])" + re.escape(c.lower()) + r"(?![a-z])", cats) for c in catsx):
        return True
    if not soft and _has(title, cfg.get("gate_keywords", [])):
        return True
    return False


def signal(s, cfg):
    title = s["title"].lower()
    win = _has(title, cfg.get("win_terms", [])) and _has(title, cfg.get("win_entities", []))
    win = 1.0 if (win or _has(title, cfg.get("opponent_loss_terms", []))) else 0.0
    outrage = min(1.0, 0.6 * _has(title, cfg.get("outrage_terms", [])))
    base = max(win, outrage)
    if base:
        base = min(1.0, base + 0.2 * _has(title, cfg.get("intensity_terms", [])))
    return base


def significance(c, cfg, settings):
    """National-significance score (0-1) and whether the hard minimums are met.
    Keys: sig_min_outlets, sig_major_tier, sig_major_outlets, sig_min, sig_weights
    {"coverage","national","amplifiers","engagement","consensus"}, sig_coverage_saturation, national_terms,
    demote_terms (local/celebrity/consumer items), sig_demotion."""
    tiers, dflt = settings["sources"]["tiers"], settings["sources"]["default_tier"]
    outlets = c.get("outlets") or {s["source"] for s in c["items"]}
    n = len(outlets)
    major_names = set(cfg.get("sig_major_outlets", []))
    major = any(tiers.get(s["source"], dflt) >= cfg.get("sig_major_tier", 0.8) or s["source"] in major_names
                for s in c["items"])
    w = cfg.get("sig_weights", {"coverage": 0.5, "national": 0.35, "amplifiers": 0.15})
    titles = " | ".join(s["title"].lower() for s in c["items"])
    nat_hits = sum(1 for t in cfg.get("national_terms", []) if re.search(r"(?<![a-z])" + re.escape(t.lower()) + r"(?![a-z])", titles))
    cov = min(1.0, (n - 1) / max(1, cfg.get("sig_coverage_saturation", 6) - 1))
    amp = c.get("signals", {}).get("amplifiers", 0.0)
    score = w.get("coverage", 0) * cov + w.get("national", 0) * min(1.0, nat_hits / 2) + w.get("amplifiers", 0) * (1.0 if amp > 0 else 0.0)
    # social engagement / account consensus can make up for thinner coverage (aligned stories only; 0 by default)
    # (engagement: only an exact / cluster-member URL match counts here; fuzzy matches stay out of the lead)
    score += w.get("engagement", 0) * c.get("engagement_exact", 0.0) + w.get("consensus", 0) * c.get("signals", {}).get("consensus", 0.0)
    rep = c["items"][0]["title"].lower()
    if _has(rep, cfg.get("demote_terms", [])):
        score -= cfg.get("sig_demotion", 0.3)
    if n < 2:
        score -= cfg.get("sig_single_source_demotion", 0.2)
    score = max(0.0, min(1.0, score))
    hard = n >= cfg.get("sig_min_outlets", 3) and major and nat_hits > 0 and score >= cfg.get("sig_min", 0.45)
    return score, hard, n


def political(s, cfg):
    return bool(_has(s["title"].lower(), cfg.get("political_terms", [])))


def order_for_lead(clusters, settings, ctx):
    """Return clusters reordered so the best lead candidates come first and
    soft-gated clusters stay out of the top-stories block."""
    cfg = config(settings, ctx)
    if not cfg.get("enabled", True):
        return clusters
    w = cfg.get("weights", {"signal": 0.45, "coverage": 0.2, "amplifiers": 0.1, "alignment": 0.15, "rank": 0.1})
    n = cfg.get("candidates", 80)
    pool = clusters[:n]
    # rank term ignores fuzzy-only engagement credit, so it can't lift a story into the lead
    lead_rank = {id(c): i for i, c in enumerate(sorted(pool, key=lambda c: -c.get("score_lead", c.get("score", 0))))}
    scored = []
    for _, c in enumerate(pool):
        rank = lead_rank[id(c)]
        rep = c["items"][0]
        if c.get("lead_excluded") or any(gated(s, cfg) for s in c["items"]):
            continue
        # blend of best and average headline signal, so one stray headline can't qualify a big cluster alone
        vals = [signal(s, cfg) for s in c["items"]]
        sig = 0.5 * max(vals) + 0.5 * sum(vals) / len(vals)
        sg = c.get("signals", {})
        score = (w.get("signal", 0) * sig + w.get("coverage", 0) * sg.get("coverage", 0)
                 + w.get("amplifiers", 0) * sg.get("amplifiers", 0) + w.get("alignment", 0) * sg.get("alignment", 0)
                 + w.get("rank", 0) * (1 - rank / max(1, len(pool)))
                 + w.get("engagement", 0) * c.get("engagement_exact", 0) + w.get("consensus", 0) * sg.get("consensus", 0))
        c["lead_signal"] = sig
        sgf, hard, n_out = significance(c, cfg, settings)
        c["significance"] = sgf
        score += w.get("significance", 0) * sgf
        scored.append((sig >= cfg.get("threshold", 0.5) and hard, score, c, political(rep, cfg) or sig > 0, sgf))
    leads = [c for ok, sc, c, _, _ in sorted(scored, key=lambda x: -x[1]) if ok]
    if not leads:  # fallback: most significant eligible political story
        pol = [x for x in scored if x[3]] or scored
        leads = [x[2] for x in sorted(pol, key=lambda x: -x[4])]
        print("lead: no story met the significance + win/outrage bar; using most significant political story")
    else:
        print(f"lead: {len(leads)} candidates passed significance and win/outrage gates")
    if leads:
        L = leads[0]
        print(f"lead: chosen story has {len(L.get('outlets', []))} outlets, significance {L.get('significance', 0):.2f}")
    head = leads[:3]
    rest = [c for c in clusters if all(c is not h for h in head)]
    # soft gate: keep sports/lifestyle etc. out of the top-stories block
    top_n = settings["placement"]["top_stories"] * 2
    ok_top = [c for c in rest if not any((gated(s, cfg, soft=True) and not c.get("featured_ok")) or gated(s, cfg)
                                         for s in c["items"])]
    early = ok_top[:top_n]
    later = [c for c in rest if all(c is not e for e in early)]
    return head + early + later
