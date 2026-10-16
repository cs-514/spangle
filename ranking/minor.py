"""Minor-figure rule: a statement or position from a minor figure (candidate in a
non-presidential race, state legislator, backbench House member, local official,
commentator) is not national news by itself. Such clusters are strongly downranked and
kept out of the lead and Top Stories, unless
  (a) a nationally prominent figure is the speaker (PROMINENT, settings "minor_figures.prominent"),
  (b) there is real action (vote, ruling, bill passing, arrest, indictment),
  (c) coverage is wide (>= min_outlets outlets including a major one), or
  (d) it is a scandal/outrage in a nationally watched race: columns allowed, lead excluded.
Generic: office titles and current national officeholders only. Settings key "minor_figures"."""
import os, re
NAME = "minor"

PROMINENT = [  # current national figures by office (president/VP, leadership, big-state governors, cabinet, justices, 2028 field)
    "trump", "vance", "biden", "harris", "obama", "walz",
    "schumer", "jeffries", "thune", "speaker johnson", "mike johnson", "scalise", "barrasso", "emmer", "pelosi",
    "newsom", "desantis", "abbott", "hochul", "shapiro", "pritzker", "whitmer", "kemp", "moore", "beshear", "youngkin",
    "rubio", "hegseth", "bondi", "patel", "noem", "bessent", "lutnick", "rfk", "kennedy", "gabbard", "leavitt",
    "roberts", "alito", "thomas", "gorsuch", "kavanaugh", "barrett", "sotomayor", "kagan", "ketanji", "kbj",
    "buttigieg", "aoc", "ocasio-cortez", "booker", "mamdani", "haley", "cruz",
]
TITLES = ["president", "vice president", "speaker", "leader", "secretary", "justice", "chief justice",
          "attorney general", "governor", "gov.", "white house", "pentagon", "scotus", "supreme court"]
STATEMENT = ["says", "said", "open to", "backs", "calls for", "vows", "wants", "urges", "floats", "pitches",
             "proposes", "suggests", "supports", "endorses", "argues", "insists", "pledges"]
NOT_SPEAKER = {"poll", "polls", "study", "report", "author", "experts", "expert", "critics", "officials", "police",
               "sources", "data", "survey", "court", "judge", "jury", "fbi", "doj", "cdc", "who", "un", "fact check:"}
MINOR = ["candidate", "nominee", "hopeful", "challenger", "state sen", "state rep", "state lawmaker",
         "state legislat", "assemblyman", "assemblywoman", "assembly member", "congressman", "congresswoman",
         "councilman", "councilwoman", "council member", "city council", "mayoral", "school board", "commentator",
         "pundit", "podcaster", "running for"]
RACE = re.compile(r"(senate|house|gubernatorial|governor's|mayoral|congressional|district) (debate|race|seat|primary|contest)")
ACTION = ["vote", "votes", "voted", "passes", "passed", "ruling", "rules", "ruled", "strikes down", "upholds",
          "bill", "signs", "signed", "law", "arrest", "arrested", "indict", "indicted", "charged", "convicted",
          "sentenced", "sued", "lawsuit", "subpoena", "raid", "executive order", "veto", "confirmed", "impeach"]
SCANDAL = ["scandal", "affair", "fraud", "corruption", "racist", "antisemit", "slur", "lied", "caught", "leaked",
           "texts", "video", "tattoo", "nazi", "communist", "threat", "violent", "assault", "drunk", "dui"]
MAJOR = ["Fox News", "NY Post", "New York Post", "Wall Street Journal", "WSJ", "AP", "Associated Press", "Reuters",
         "New York Times", "Washington Post", "Politico", "Axios", "CNN", "NBC News", "CBS News", "ABC News",
         "Washington Examiner", "Daily Wire", "Breitbart", "Washington Free Beacon", "National Review"]


def _has(text, words, whole=False):
    tail = r"(?![a-z0-9])" if whole else ""
    return any(re.search(r"(?<![a-z0-9])" + re.escape(w) + tail, text) for w in words)


def _norm(s):
    return " " + re.sub(r"\s+", " ", (s or "").lower().replace("’", "'")) + " "


# Sitting U.S. senators and governors are national figures: detected by title ("Sen.", "Senator",
# "Gov.", "Governor", "(R-ME)"-style tags), but not "state senator", "former/ex-", or a race for the seat.
OFFICE = re.compile(r"(?<!state )(?<!former )(?<!ex-)(?<!for )\b(sen\.|senator|gov\.|governor)\s+[a-z]"
                    r"|\((?:r|d|i)-[a-z]{2}\)")
POLL = re.compile(r"(?<![a-z])(poll|polls|polling|survey)(?![a-z])")


def classify(items, outlets=(), cfg=None):
    """None (not a minor-figure statement or excepted) | 'minor' | 'minor_scandal'."""
    cfg = cfg or {}
    prom = PROMINENT + [p.lower() for p in cfg.get("prominent", [])]
    major = MAJOR + list(cfg.get("major_outlets", []))
    titles = _norm(" ".join(s["title"] for s in items))
    body = _norm(" ".join(s["title"] + " " + (s.get("desc") or "")[:300] for s in items))
    if POLL.search(titles):                                       # polls are data, not a figure's statement
        return None
    if not _has(titles, STATEMENT, True):
        return None
    if _has(titles, prom, True):                                  # (a) a prominent figure is in the story
        return None
    if _has(titles, ACTION):                                      # (b) real action
        return None
    if len(outlets) >= int(cfg.get("min_outlets", 5)) and any(o in major for o in outlets):
        return None                                               # (c) very wide coverage
    # speaker = the words right before the first statement verb in a headline
    for s in items:
        t = _norm(s["title"])
        m = re.search(r"(?<![a-z0-9])(" + "|".join(map(re.escape, STATEMENT)) + r")(?![a-z])", t)
        if not m:
            continue
        before = t[:m.start()].split()[-4:]
        speaker = " ".join(before)
        if not before or before[-1].strip(",:'\"‘“") in NOT_SPEAKER:
            continue                                              # institutions / polls are not "figures"
        if _has(" " + speaker + " ", TITLES):
            return None                                           # (a) speaker identified by a national office
        name = re.escape(before[-1].strip(",:'\"‘“’s"))
        if OFFICE.search(speaker + " x") or re.search(
                r"(?<!state )(?<!former )(?<!ex-)\b(sen\.|senator|gov\.|governor)\s+(?:[a-z.'-]+\s+){0,2}" + name + r"\b"
                r"|\b" + name + r"\s+\((?:r|d|i)-[a-z]{2}\)", body):
            return None                                           # (a) the speaker is a sitting senator / governor
        break
    else:
        return None
    if not (_has(body, MINOR) or RACE.search(body) or re.search(r"\b(dem|democrat|gop|republican) [a-z]+ [a-z]+ said", body)):
        return None
    return "minor_scandal" if _has(titles, SCANDAL) else "minor"


def compute(clusters, settings, ctx):
    cfg = settings.get("minor_figures") or {}
    if cfg.get("enabled") is False:
        return None
    demote = float(cfg.get("demotion", 0.05))
    out, n = {}, 0
    for c in clusters:
        k = classify(c["items"], c.get("outlets") or (), cfg)
        out[c["id"]] = 1.0
        if k:
            n += 1
            if os.environ.get("MINOR_DEBUG"):
                print("  minor:", k, c["items"][0]["title"][:90])
            c["lead_excluded"] = True
            if k == "minor":
                out[c["id"]] = demote
                c["top_excluded"] = True
    print(f"signal minor: {n} minor-figure clusters flagged")
    return out
