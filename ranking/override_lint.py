"""Override data checks. headline_overrides.json is edited by an hourly routine, so content problems in it
must never block a deploy: invalid entries are dropped at load, everything else is reported as a warning
(counts only in logs) and fixed by clean() at display time or by the rewrite queue."""
import re

WARN_REASONS = ("obscure_acronym", "too_long", "fragment", "double_quotes", "capitalized_preposition")


def sanitize(d):
    """(clean dict, dropped keys): drop non-string / empty values and non-string keys; strip whitespace."""
    out, dropped = {}, []
    for k, v in (d or {}).items():
        if not isinstance(k, str) or not k.strip() or not isinstance(v, str) or not v.strip():
            dropped.append(k)
            continue
        out[k.strip()] = re.sub(r"\s+", " ", v).strip()
    return out, dropped


def lint(d, sty=None):
    """{reason: [keys]} for content-quality issues (warnings, never errors)."""
    from . import headline as h
    sty = sty or h.style()
    out = {r: [] for r in WARN_REASONS}
    clean_d, dropped = sanitize(d)
    out["invalid"] = dropped
    for k, v in clean_d.items():
        try:
            c = h.clean(v, sty)[0] or v
        except Exception:
            out["invalid"].append(k)
            continue
        if any(q in v for q in '“”"'):
            out["double_quotes"].append(k)
        if re.search(r"\s(With|From|Into|Onto|Upon)\s", v.split(": ")[-1] if ": " in v else v[1:]):
            out["capitalized_preposition"].append(k)
        if h.obscure_acronyms(c, sty):
            out["obscure_acronym"].append(k)
        if h.too_long(c, sty):
            out["too_long"].append(k)
        if h.fragment(c):
            out["fragment"].append(k)
    return {r: ks for r, ks in out.items() if ks}


def summary(d, sty=None):
    issues = lint(d, sty)
    return ", ".join(f"{r} {len(ks)}" for r, ks in sorted(issues.items())) or "none"
