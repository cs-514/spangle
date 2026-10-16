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

### Automatic shortening (before queueing)
Headlines over 70 characters or 12 words get safe, meaning-preserving trims in this order, stopping as
soon as the headline fits: drop parentheticals; drop a leading "A/An/The"; drop filler adverbs (Just,
Now, Officially, Actually, Literally, Even); drop passive auxiliaries ("Was Convicted" → "Convicted");
keep the part before a dash or colon if it stands alone; finally cut the shortest trailing
prepositional phrase or comma clause that makes it fit (at least 6 words stay). Never an ellipsis, never
a mid-phrase cut. If nothing safe works, the full headline shows and goes to the rewrite queue.
Example: "A Trans Substitute Teacher Was Just Convicted for Threatening ‘Murder Spree’ at Virginia High
School" → "Trans Substitute Teacher Convicted for Threatening ‘Murder Spree’".

## Cut-off source titles
A source title looks cut off if it ends with an ellipsis or mid-word, or its last word is a strict
prefix of a word in the URL slug, or is rare today while a longer word starting with it is common
("Investigatio" vs "Investigation"). The build completes the word from the slug or today's headlines;
otherwise the story prefers a sibling headline, goes to the rewrite queue, and can never be the lead.

## Meta line
The outlet's display name (never a raw domain such as "lifezette.com"), then the time:
"American Greatness · Oct 15, 10:02 AM" — all displayed times are US Eastern (America/New_York, DST-aware), 12-hour with AM/PM, no zone suffix on items; the zone appears once, in the header ("Updated Oct 15, 9:27 PM ET"). No "UTC" anywhere on the page; ranking stays in UTC internally. No "+N outlets" count (coverage is used only for ranking).
No Opinion tags (Drudge-style); no leading or doubled "·". The Quote of the Day shows a small QUOTE kicker above its headline, then the quote text, then the source line "Author · Work, locator".

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
| VDH | Victor Davis Hanson (person-specific; possessive → VDH’s) |

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

## Drop redundant possessives

When a named subject opens the headline, drop a redundant **her/his/their/its** before a noun:
*Omar Probe Aims to Strip Her Citizenship, Deport Her* → *Omar Probe Aims to Strip Citizenship, Deport Her*.
Keep object pronouns (*Deport Her*). Keep the pronoun after a preposition or conjunction (*Over Her Remarks*),
before *own* or a family word (*His Own Team*, *Her Husband*), before a quoted word, and after a generic
or pronoun opener (*The…*, *She…*). Only the first match is dropped. Config: `drop_possessives` in
`headline_style.json`. Tests: `tests/test_possessives.py`.

## Trim quoted labels

When a label is quoted, cut it down to the core label and drop the filler around it:
*Trump says Abdul el Sayed is ‘100%’ a ‘Muslim Brotherhood guy’* → *Trump says Abdul el Sayed is ‘100%’ ‘Muslim Brotherhood’*.
A trailing generic noun inside the quotes (guy, person, type, figure, …) is dropped when the quote has at least
two words, along with the a/an just before the quote. Leading *kind of / sort of / type of* is dropped too (‘kind
of a joke’ → ‘joke’). Only curly-quoted spans are touched, and the label keeps at least one word. Config:
`trim_quoted_labels` in `headline_style.json`. Tests: `tests/test_quoted_labels.py`. (Smart quotes also
treat ‘100%’ as a quote, while ’90s and ’24 stay elisions.)

## Numerals and small words

- **Use digits, even for 1–9.** *5 Positions Talarico Abandoned in 1 Night*, not *…In One Night*. Pronoun *one*
  stays a word (*No One*, *One of Them*, *One Another*, *Someone*).

Config: `numerals` in `headline_style.json`. Tests: `tests/test_numerals_case.py`.

## Title case (AP/Chicago)

Every headline is normalized to title case, and sentence-case headlines are converted. Lowercase *a, an, the,
and, but, or, nor, as, at, by, for, if, in, of, on, to, vs* except as the first or last word, after a colon or
dash, or at the start of a quote. Capitalize everything else, including both parts of a hyphenated word
(*Live-Stream*) and phrasal particles (*Take Up*; *Up* always stays capitalized). Words that already have
capitals are never lowercased: acronyms, the style abbreviations (SCOTUS, DOGE, VDH, DEMS, GOP), *McDonald*,
*iPhone*, ALL-CAPS lines. Lowercase name particles before a name stay as they are (*el Sayed*, *bin Salman*).
The Quote of the Day is not touched.

- *DOGE Gets Its Day at the Supreme Court As Justices Take Up Trump Administration Appeal* →
  *DOGE Gets Day at SCOTUS as Justices Take Up Trump Administration Appeal*
- *Netanyahu rival vows to end Hamas rule within 18 months if elected* →
  *Netanyahu Rival Vows to End Hamas Rule Within 18 Months if Elected*

Config: `title_case` in `headline_style.json`. Tests: `tests/test_title_case.py`.

## No contentless headlines

A headline of three words or fewer with no verb, or a bare proper name (e.g. *Angie Nixon*), counts as
bland. Spangle tries a sibling headline first, then the article's `og:title`/`<h1>`. If neither works,
the item is **dropped from the page** and queued (`reason: "contentless"`) until an override exists.

## Smart quotes — always curly

All displayed text (headlines, overrides, rewrites, Quote of the Day headline/text/tooltip,
attribution, meta lines) uses curly quotes ‘ ’ “ ”, never straight ' ". `smartquotes()` in
`ranking/headline.py` runs **after** all other style rules (toggle: `"smart_quotes": true` in
`headline_style.json`). Rules: apostrophes in words and leading elisions (’90s, ’em, ’tis) → ’;
quotes after start/space/([{—/– open (‘ “); everything else closes (’ ”). HTML entities
(`&#39;`, `&quot;`) are decoded first; only text is transformed, never URLs or attribute names.
Tests: `python3 -m unittest tests/test_smartquotes.py`.

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
