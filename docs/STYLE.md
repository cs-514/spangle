# Spangle headline style manual

A living Drudge-style guide for every displayed headline. Extend it freely; the machine-applicable rules live in [`headline_style.json`](../headline_style.json) and are applied automatically on every build. Manual and AI rewrites go in [`headline_overrides.json`](../headline_overrides.json).

## Principles

1. **Brevity.** Target ≤ 10 words / ~70 characters. Cut until it still makes sense.
2. **Attention-grabbing.** Lead with the news, not the context. Names, numbers and verbs first.
3. **Active voice, present tense.** "SCOTUS Blocks Ban" beats "A Ban Was Blocked by the Court."
4. **Strong verbs.** Wins, Blocks, Seizes, Slams, Exposes, Flips, Passes, Indicts, Fires, Freezes.
5. **Concrete names and numbers.** "Ilhan Omar", "$2.4B", "9th Circuit", "47%" — not "a lawmaker", "funding", "a court", "a majority".
6. **Faithful.** Never invent facts. The rewrite must still describe the linked article. No clickbait lies.
7. **No academic phrasing.** Drop "approach", "framework", "analysis", "jurisprudential", "symposium", "considerations", "project", "perspectives".
8. **No colon-plus-subtitle.** One punchy line, not "Topic: Long Explanation Of Topic".
9. **No trailing site names, tags or clickbait chrome.** Strip "[WATCH]", "[VIDEO]", "Opinion:", "— Exclusive", " | Fox News".
10. **All-caps is fine for the lead.** The page already uppercases the lead visually via CSS weight and color; keep the text Title Case or ALL CAPS as the rewrite prefers. Columns stay mixed case.


## Trim rule (over-length headlines)

If a headline still exceeds ~70 characters / 10–12 words **after** deterministic cleanup
(abbreviations, strip `Opinion:` / `[WATCH]` / trailing site names / chrome parentheticals):

1. Prefer a shorter non-bland sibling headline from another outlet covering the same story.
2. Otherwise queue it for a **trim rewrite** (`reason: "too_long"` in the rewrite queue).
3. **Never truncate mid-phrase on the page.** Headlines wrap; they are not ellipsized.

When trimming by hand or AI:
- Cut filler ("This", "Brought to You by", "Everything We Know About", "Here's Why").
- Keep the **subject** and the **punchy verb / adjectives**.
- No loss of meaning — the rewrite must still describe the linked article.
- Example: *This Condescending, Preachy, Woke Political Lecture Brought to You by Ticketmaster*
  → *Condescending, Preachy, Woke Political Lectures from TicketMaster*

## Abbreviations (use these when they shorten)

| Write | For |
|---|---|
| SCOTUS | Supreme Court (of the United States) |
| POTUS | President of the United States |
| VP | Vice President |
| DOJ | Department of Justice / Justice Department |
| FBI | Federal Bureau of Investigation |
| DHS | Department of Homeland Security |
| ICE | Immigration and Customs Enforcement |
| CBP | Customs and Border Protection |
| GOP | Republicans / Republican Party (when it shortens) |
| DEMS | Democrats / Democratic Party (when it shortens) |
| SEC/STATE | Secretary of State |
| AG | Attorney General |
| D.C. | Washington, D.C. / District of Columbia |
| Fed | Federal Reserve |
| USA | United States of America |
| NYC | New York City |
| Gov. | Governor (before a name) |
| Rep. | Representative (before a name) |
| Sen. | Senator (before a name) |
| Pentagon | Department of Defense / Defense Department |
| Hill | Congress (when speaking of Capitol Hill) |

Prefer the short form only when it is clear in context. "GOP Senators Pass Bill" is fine; "GOP" alone as a subject usually is too.

### SCOTUS — never "the SCOTUS"

**Never put "the" before SCOTUS.** Write `SCOTUS`, not `the SCOTUS`.

Deterministic cleanup in `headline_style.json` (applied to every displayed headline and override):

| From | To |
|---|---|
| the Supreme Court / The Supreme Court | SCOTUS |
| the U.S. Supreme Court / U.S. Supreme Court | SCOTUS |
| the SCOTUS / The SCOTUS | SCOTUS |

Examples: *DOGE Gets Its Day at SCOTUS* · *Kamala: DEMS Will Pack SCOTUS* · *SCOTUS Crushes DEM Challenges*.

## Patterns to prefer

- **X Does Y To Z.** "FBI Seizes Omar Phone in Immigration Raid"
- **Number + Noun.** "9th Circuit Blocks Newsom ICE Law"
- **Name + Verb + Object.** "Trump Fires Fed Governor"
- **Quote-as-punch.** Keep a short, sharp quote only when it *is* the news.

## Patterns to avoid

- Academic: "A Jurisprudential Approach to the Six Conservative Justices…"
- Soft: "Everything We Know About…", "Here's Why…", "What to Know About…"
- Subtitle pile-ups: "Topic: Subtopic — More Context | Outlet"
- Sports/lifestyle chrome in political slots (those are gated out of the lead anyway)

## How rewrites enter the site

1. Deterministic rules in `headline_style.json` run on every build (abbreviations, filler stripping, max length soft-trim).
2. Manual pins in `manual_links.json` can set `title` (and optional `archive_url`).
3. AI / human rewrites: the box script `/workspace/rewrite_queue.py` queues bland headlines; the parent agent (or a human) writes punchy replacements into `/workspace/rewrites_done.json`; `rewrite_queue.py apply` commits them as `headline_overrides.json` and triggers the hourly workflow.

See [CONTROLS.md](CONTROLS.md) for the knobs.
