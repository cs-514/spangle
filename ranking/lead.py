"""Lead eligibility and lead scoring.

Public settings ("lead" in settings.json) hold generic defaults; the private config
(ALIGNMENT_CONFIG key "lead") may override any key. Keys:
  gate_paths / gate_categories / gate_keywords : hard topic gate (sports, lifestyle, ...)
  soft_gate_paths / soft_gate_categories      : softer gate for the top-stories block
  political_terms                              : marks a story as political/cultural
  win_terms, win_entities, opponent_loss_terms : "win" lexicon (term + entity, or opponent-loss phrase)
  outrage_terms, intensity_terms               : "outrage" lexicon and intensity boosters
  threshold                                    : minimum win/outrage signal for the lead
  weights                                      : {"signal", "coverage", "amplifiers", "alignment", "rank"}
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
    scored = []
    for rank, c in enumerate(pool):
        rep = c["items"][0]
        if c.get("lead_excluded") or any(gated(s, cfg) for s in c["items"]):
            continue
        # average across the cluster's headlines, so one stray headline can't qualify a story
        sig = sum(signal(s, cfg) for s in c["items"]) / len(c["items"])
        sg = c.get("signals", {})
        score = (w.get("signal", 0) * sig + w.get("coverage", 0) * sg.get("coverage", 0)
                 + w.get("amplifiers", 0) * sg.get("amplifiers", 0) + w.get("alignment", 0) * sg.get("alignment", 0)
                 + w.get("rank", 0) * (1 - rank / max(1, len(pool))))
        c["lead_signal"] = sig
        scored.append((sig >= cfg.get("threshold", 0.5), score, c, political(rep, cfg) or sig > 0))
    leads = [c for ok, sc, c, _ in sorted(scored, key=lambda x: -x[1]) if ok]
    if not leads:  # fallback: highest-ranked eligible political story
        leads = [c for ok, sc, c, pol in scored if pol] or [c for _, _, c, _ in scored]
        print("lead: no story met the win/outrage threshold; using fallback")
    else:
        print(f"lead: {len(leads)} eligible candidates above threshold")
    head = leads[:3]
    rest = [c for c in clusters if all(c is not h for h in head)]
    # soft gate: keep sports/lifestyle etc. out of the top-stories block
    top_n = settings["placement"]["top_stories"] * 2
    ok_top = [c for c in rest if not any(gated(s, cfg, soft=True) or gated(s, cfg) for s in c["items"])]
    early = ok_top[:top_n]
    later = [c for c in rest if all(c is not e for e in early)]
    return head + early + later
