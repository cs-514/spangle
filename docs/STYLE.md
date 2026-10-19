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
"American Greatness · Oct 15, 10:02 AM" — all displayed times are US Eastern (America/New_York, DST-aware), 12-hour with AM/PM, no zone suffix on items; no zone label anywhere (no "ET"). Header: "Friday, October 16, 2026 · Updated 6:38 AM" (Eastern date; the Updated part shows time only, each half kept unbroken so mobile wraps only at the "·"). No "UTC" anywhere on the page; ranking stays in UTC internally. No "+N outlets" count (coverage is used only for ranking).
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
| Dems | Democrats / Democratic Party (when it shortens); *Dem* for one |
| Sec. of State | Secretary of State |
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

Examples: *DOGE Gets Its Day at SCOTUS* · *Kamala: Dems Will Pack SCOTUS* · *SCOTUS Crushes Dem Challenges*.

## Only true acronyms are ALL CAPS

ALL CAPS is for acronyms and initialisms only (DOJ, FBI, SCOTUS, DOGE, GOP, MAGA, NATO; the `acronyms` lists in
`headline_style.json`). *Dems*, *Dem* and *Sec. of State* are abbreviations, not acronyms, so they are never
capitalized. `fix_allcaps()` runs before title case: known shouting forms are mapped (`allcaps_words`:
DEMS → Dems, SEC/STATE → Sec. of State, WI → Wis.), and other all-caps words of 4+ letters or common short words
become title case (*BIG MONEY* → *Big Money*, *EVISCERATES* → *Eviscerates*). Unknown 2–3-letter tokens are
assumed to be acronyms.

## Only acronyms every reader knows

Headlines use only acronyms a general national reader instantly recognizes: FBI, DOJ, CIA, ICE, GOP, SCOTUS,
NATO, DOGE, NCAA (`acronyms.well_known`). Obscure ones (school initials, local agencies, niche orgs, state postal
codes, borderline military commands like CENTCOM) are replaced with a plain generic descriptor, possessive where
natural, keeping the headline the same length or shorter:

- *Ex-SJSU Coach Sues over ‘Trump Lover’ Barbs* → *College’s Ex-Coach Sues over ‘Trump Lover’ Barbs*
- *NRSC Ad Mocks Peltola* → *GOP Senate Arm’s Ad Mocks Peltola*
- *FBI Probes Letters with DSA-Linked Address* → *FBI Probes Letters with Socialist-Linked Address*
- *CENTCOM Says Strait Stays Open* → *U.S. Military Says Strait Stays Open*

`acronyms.case_only` keeps the casing of known-but-obscure acronyms when a source uses them (so they are never
mangled to *Sjsu*), but any displayed headline with an ALL-CAPS token not in `well_known` is queued for rewrite
with reason `obscure_acronym` (`obscure_acronyms()` in `ranking/headline.py`). Hyphen parts are checked on
their own (*Ex-SJSU*); dotted forms must be listed dotted (*U.S.*, *S.C.*); Roman numerals, number-letter tokens
(*F-35*, *Q3*), `well_known_phrases` (*MS Now*) and two-letter initials before a name (*JD Vance*) are not
flagged. A rewrite that still uses an obscure acronym is rejected. The other house rules still apply (single
curly quotes; *with*, *to*, *over* lowercase; no orphans; *Dems*, never *DEMS*).

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
and, but, or, nor, as, at, by, for, if, in, of, on, to, vs, with, from, into, onto, upon* except as the first or last word, after a colon or
dash, or at the start of a quote. Capitalize everything else, including both parts of a hyphenated word
(*Live-Stream*; see the compound rules below) and phrasal particles (*Take Up*; *Up* always stays capitalized). Words that already have
capitals are never lowercased: acronyms, the style abbreviations (SCOTUS, DOGE, VDH, GOP), *McDonald*,
*iPhone*, ALL-CAPS lines. Lowercase name particles before a name stay as they are (*el Sayed*, *bin Salman*).
The Quote of the Day is not touched.

- **Hyphenated compounds (Chicago):** capitalize every element, including the second (*Fast-Moving*,
  *Anti-Israel*, *Trump-Appointed*, *18-Year-Old*), except articles, prepositions and conjunctions in the
  middle (*Soft-on-Crime*, *Up-to-Date*, *Mother-in-Law*; list in `title_case.hyphen_small_words`). Elements that
  already have internal capitals are kept (*U.S.-China*, *COVID-19*, *McCarthy-Era*). Brand spellings go in
  `title_case.preserve` (*Chick-fil-A*).
- **Acronyms inside compounds:** each part of a hyphenated ALL-CAPS token is judged on its own. A part stays
  all caps when it is a known acronym (`acronyms.well_known` or `case_only`, e.g. *SJSU*, *CENTCOM*) or 3+ consonant-only letters
  (*NTSB*, *NRSC*); other parts become Title Case (*EX-SJSU* → *Ex-SJSU*). The same rule applies to
  overrides, so a hand-written *Ex-SJSU* is never mangled to *Ex-Sjsu*.
- **No fragments:** a trim (`shorten`) is rejected when it would leave a fragment: it ends on a dangling
  word (*that, which, of, the, and* …), it drops every finite verb the original had (*‘Vast Majority’ of Iran’s
  Attempted Attacks* from *… Are Unsuccessful, CENTCOM Spokesman Says*), it stops a *that/which/who* clause
  before its verb (*Racist Claim That Arab Mothers*), or it ends on a time unit cut from *After/Before …*
  (*Rally Comes Days*). Dropping a whole dash/colon tail is fine. Any displayed headline that still reads as a
  fragment is queued for rewrite (`reason: "fragment"`); the fix is an override with a verb. An override
  also applies when link cleanup relinks a story to the overridden URL after the headline was chosen.
- **Every displayed headline is a complete thought** (`headline.incomplete`), whether it is the source
  title, a shortened trim or an override. Flagged kinds: `cut_off` (the rules above), `no_finite_verb`
  (a noun phrase: *Trump’s Big Week*), `missing_complement` (a verb that needs a place left without one:
  *Why Obama Admin Put Abdul El-Sayed’s Sister-in-Law*, trimmed from *… on Terror Watch List*) and
  `cut_explainer` (a *Why/How …* explainer cut short). Accepted headline-ese: a predicate participle
  (*Ex-Coach Arrested*, *Dad Tied to …*), the headline future (*Trump to Sign*), a plural subject with a
  base verb (*Media Skip …*), a predicate progressive (*Formula Working Against Trump*), and speaker or label
  colons (*Homan: …*, *WSJ: …*). Flagged headlines are queued (`reason: "fragment"`, `fragment_kind`), and the
  rewrite tool rejects a rewrite that is still a fragment. Imprimis essays keep their possessive form
  (exempt from `no_finite_verb` only).
- **Dashes:** a dash between words or clauses is a closed em dash with no spaces: *Watch List—As He
  Insists*. `--` (spaced or not), a spaced em dash ` — ` and a spaced en dash ` – ` all become `—`
  (`headline.dashes`). Number ranges keep the en dash, closed (*10 – 12* → *10–12*); hyphens and unspaced
  en dashes between words (*Harris–Walz*) are untouched. Outlet tails (*… — NY Post*) are stripped first,
  and the shortening step still drops a whole dash tail. After a dash, Chicago style: minor words (*and, but, or,
  nor, for, as, the, a, an, to, of, in, on, at, by, with* …) stay lowercase (*Shows—and Leaves Unanswered*,
  *Watch List—as He Insists*) and major words stay capitalized (*Burning—Is America Next?*). A colon or a
  real sentence break still capitalizes the next word (*Abortions. But Why?*, *Homan: The Wall Works*). The same rule applies to the QOTD quote and
  headline, hover tooltips, rewrites (`rewrite_queue.py apply` normalizes them) and the QOTD bank; the
  QOTD validator rejects spaced dashes and `--`. No orphans: the closed dash stays a line-break point,
  so only the words after the last dash are glued with a no-break space, and a last chunk like
  *Nothing—Wrong* is never glued across the dash.
- **Sentence starts:** the first word after a real sentence break (`.` `?` `!`, or a colon, including after an
  opening quote) is capitalized: *Abortions. But Why?* Ellipses (*. . .*, *...*) and abbreviations (*U.S.*,
  *D.C.*, *Mr.*, *Gov.*) are not breaks, and neither is punctuation inside a closing quote mid-headline:
  *Asked ‘Why?’ and Walked Out*.
- **"to" is always lowercase** unless it is the first word or starts a sentence, even in infinitives and as the
  last word: *Wants to See*, *Vows to Fight On*.
- **Short prepositions (under 5 letters):** *with* was capitalized because the old list stopped at 3-letter
  words. *with, from, into, onto, upon* are now lowercase mid-headline (*Partied with Fugitives*, *Probe into
  Omar*, *Boot Judge from Trump’s Fight*). They are almost never adverbs, so no exception is needed; the usual
  boundaries still apply (*With Friends Like These*, *Crime: With Friends*, *Who Is He With?*).
- **"over" depends on its job.** As a preposition it is lowercase (*Sues Governor over Eligibility Rule*, *Fight
  over $1M Deal*). As an adverb or phrasal particle it stays capitalized: after a verb like *take, hand, turn,
  win, roll, blow, boil, spill, flip, pass, sign, fork, think, look, carry, come, go* (*Takes Over Twitter*,
  *Hands Over Files*, *Won Over Voters*), in *Game Over* / *It’s Over*, at the end, or before punctuation
  (*Fight Over, Says Trump*). The verb list is `title_case.particle_prepositions.over` in
  `headline_style.json`; add a verb there when a new phrasal use turns up.
- **Adverbs and particles are never on the list:** *Fires Back*, *Shuts Down*, *Takes Up*, *Weighs In* (last word),
  *Off*, *Out*, *Up*, *Down*, *Back* always stay capitalized. *over* is the only word that needs the
  preposition/particle test. (*in* and *on* were already lowercase; their rare particle uses mid-headline,
  e.g. *Cracks Down on*, read fine lowercase.)

## No orphans (line breaks)

A multi-line headline never ends on a one-word line (*…Totally Unfit for / Use*, *…Ban / ICE*, *…Back*). The
renderer joins the **last two words of every headline** (lead, Top Stories, columns and the Quote of the Day
headline) with a non-breaking space (`&nbsp;`), so they always wrap together. Exception: if the last two words
together are longer than 20 characters the space is left alone, so a long pair can't overflow a narrow phone
column. CSS `text-wrap: pretty` is also set on headline links as a progressive enhancement (browsers that support
it balance the last lines further; others ignore it). The column-balance height estimate wraps the joined pair as
one word. Code: `no_orphan_html` / `no_orphan_text` in `aggregator.py`. Tests: `tests/test_columns.py`.

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

**Headlines quote with single quotes.** In headlines only (feed titles, overrides, rewrites, the QOTD
headline), quotations use ‘…’, not “…” or straight "…": *Dems’ ‘Affordability’ Pitch*, not *Dems’ “Affordability”
Pitch*. A quote nested inside a quote takes double: *Said ‘I Won’t Say “Never”’*. Apostrophes are untouched
(*Dems’*, *Won’t*, *’90s*). The Quote of the Day body text keeps normal double quotes. `headline_quotes()` runs at
the end of `clean()` (toggle: `"single_quotes": true` in `headline_style.json`).

## Patterns to prefer

- **X Does Y To Z.** "FBI Seizes Omar Phone in Immigration Raid"
- **Number + Noun.** "9th Circuit Blocks Newsom ICE Law"
- **Name + Verb + Object.** "Trump Fires Fed Governor"
- **Quote-as-punch.** Keep a short, sharp quote only when it *is* the news.

## Build from the most quotable line

**Rare and opportunistic, not automatic.** Only when the article contains a genuinely outrageous, eye-catching
line, either a quote or the writer's own wording, that clearly beats any normal rewrite, build the headline from
it. Otherwise rewrite normally. Irreverent wording is fine. Keep attribution accurate: never
put a writer's or source's words in someone else's mouth (no "Gillis:" prefix for the writer's line).

- *Shane Gillis Outcry Shows We Need More Public Shaming, At The Gym And Everywhere* → *Gym Booty Shorts Are Lululemon Set’s Version of Homeless Guy Dropping Deuce in Park*
  (the Lululemon line is the Federalist writer's, not Gillis's, so it carries no attribution to him)

## Patterns to avoid

- Academic: "A Jurisprudential Approach to the Six Conservative Justices…"
- Soft: "Everything We Know About…", "Here's Why…", "What to Know About…"
- Subtitle pile-ups: "Topic: Subtopic — More Context | Outlet"
- Sports/lifestyle chrome in political slots (those are gated out of the lead anyway)

## Academic / explainer posts (Volokh and similar)

Law-review notices, docket-name headlines and legal retrospectives (`ranking/academic.py`, Volokh Conspiracy
by default; see `settings.json` `"academic"`) are flagged `academic`. Every placed academic item without an
override goes to the rewrite queue with reason `academic`:

- Rewrite around the **news hook**, using the case's **popular name or the issue**, never the docket name.
  Example: "How Matal v. Tam Became Free Speech Case" → "‘Slants’ Case Backstory: SCOTUS Got Band’s Founder Wrong".
- Same house style: Drudge compression, title case, curly quotes, numerals.
- No newsworthy hook (pure legal-academic retrospective, nothing current)? Leave it. Unless its headline hits a
  news hook or it has an override, the story is kept out of the lead and Top Stories and scored `penalty`
  (or dropped with `"drop": true`).

## Imprimis headlines

Imprimis titles read like lecture or course titles: flat noun phrases such as *The X of Y*, *Understanding Z*,
*How to Think About W*. They always need recasting:

1. **Short, punchy, thesis-carrying:** 3–6 words that state the essay's argument and stance, faithful to it.
2. **Sharp evaluative words:** 1–2 adjectives or verbs that carry the thesis (*alarming, disturbing, persistent,
   failed, dangerous, forgotten*).
3. **No articles.**
4. **Vary the form and pick the punchiest:** subject as possessive or lead noun (*Socialism’s Persistent, Disturbing
   Rise*), parallel fragments, a verb-driven claim, a question, or a quoted line. The possessive is one option, not
   the rule.

Example: *The Rise of Democratic Socialism* → *Socialism’s Persistent, Disturbing Rise*.

How it runs: every Imprimis item is queued for the box rewriter with reason `imprimis`, this guidance, a few-shot
example and the essay's opening paragraphs. Until a rewrite lands, `imprimis_recast()` in `ranking/headline.py`
applies a mechanical fallback (*The Rise of X* → *X’s Rise*, *The Hard Truth About X* → *X’s Hard Truth*,
*Recovering the Lost Art of X* → *X’s Lost Art*, *Learning From X* → *Lessons of X*). Titles it can't recast safely
(questions, clauses, gerund subjects) are left as they are. A saved override in `headline_overrides.json` always wins.

## How rewrites enter the site

1. Deterministic rules in `headline_style.json` run on every build (abbreviations, filler stripping, max length soft-trim).
2. Manual pins in `manual_links.json` can set `title` (and optional `archive_url`).
3. AI / human rewrites: the box script `/workspace/rewrite_queue.py` queues bland headlines; the parent agent (or a human) writes punchy replacements into `/workspace/rewrites_done.json`; `rewrite_queue.py apply` commits them as `headline_overrides.json` and triggers the hourly workflow.

See [CONTROLS.md](CONTROLS.md) for the knobs.

## Quote of the Day headlines
A QOTD headline is punchy and drawn from the quote itself; a famous line can be the headline
(*Mr. Gorbachev, Tear Down This Wall!*, *The Power to Tax Involves the Power to Destroy*,
*All Warfare Is Based on Deception*). Use a teaser instead only when the payoff is a surprise twist
the headline would spoil. Bank entries may carry a bespoke `headline` field (e.g. st-006,
*Supreme Excellence Against Adversaries*); entries without one fall back to the quote's opening words.

## Compression
Shorter, punchier headlines (QOTD and rewrites):
- Drop leading articles (The / A / An) unless part of a name (*The Hill*, *The Almighty*).
- Cut linking or filler verbs (involves, is, are, means, represents) when parallel noun phrases carry
  the meaning, and join the fragments with a comma: *The Power to Tax Involves the Power to Destroy* →
  **Power to Tax, Power to Destroy**.
- Strip throat-clearing ("Here’s why", "What to know").
- Keep iconic verbatim lines as spoken (*Mr. Gorbachev, Tear Down This Wall!*) and chosen headlines
  (*Supreme Excellence Against Adversaries*).
- News: never drop an action verb; the verb is often the story. The automatic compressor
  (`headline.compress`, `headline_style.json` → `compression`) only drops a leading article and turns
  *X Involves/Means/Equals Y* into *X, Y* when the two sides are short parallel phrases.

## Judicial quote sources
Court-opinion quotes (Scalia, Marshall, Bork) display as **Author, *Case Name* (Year)**, with the case
name italicized: *Antonin Scalia, District of Columbia v. Heller (2008)*. No reporter citations
(554 U.S. 570, 5 U.S. 137, 750 F.2d 970, S. Ct., L. Ed.) and no "(dissenting)"/"(concurring)" on the page;
the full cite stays in the bank's `citation` field and the quote links to the opinion text. The renderer
strips reporter cites as a safety net.
