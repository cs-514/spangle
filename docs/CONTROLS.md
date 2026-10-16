# Spangle controls

All public tuning lives in [`settings.json`](../settings.json) at the repo root.

**How to change a setting:** open `settings.json` on GitHub, click the pencil (Edit), change the value, and commit.
The next hourly build (at :17 past each hour) picks it up. To apply it right away, go to
**Actions → Build and deploy → Run workflow**, or run `gh workflow run build.yml -R cs-514/spangle`.
Keep the file valid JSON: double quotes, and no trailing commas.

## How ranking works

1. Feeds are fetched. Then paywalled domains, duplicates and items older than `recency.max_age_hours` are dropped.
2. Headlines are **clustered**, so the same story from several outlets becomes one cluster.
3. Each signal module in `ranking/` returns a score from 0 to 1 per cluster. The final score is the weighted sum.
   If a signal is unavailable (disabled, blocked or no token), its weight is spread proportionally across the others.
4. Social signals are only queried for the top `social.candidates` clusters from the first pass, to keep request counts low.
5. Placement: the #1 cluster becomes the red lead. The next `top_stories` become Top Stories, and the rest fill the
   columns. Each cluster shows only one link (the highest-tier outlet), and outlet caps apply.

## `weights`: how much each signal counts (they're normalized, so they don't need to add up to 1)

| key | default | signal |
|---|---|---|
| `recency` | 0.25 | Freshness, with exponential decay |
| `coverage` | 0.25 | How many distinct outlets ran the story |
| `source` | 0.10 | Tier of the best outlet in the cluster |
| `alignment` | 0.20 | Editorial alignment from the private config (see below) |
| `amplifiers` | 0.0 | Stories linked to or echoed by configured public feeds (feed list in the private config) |
| `framing` | 0.0 | Headline framing toward configured entities (lexicon in the private config). It also marks clusters to keep out of the lead. |
| `curated_by_aggregators` | 0.15 | A human-curated aggregator (Bongino Report) currently links to the story |
| `google_news` | 0.08 | Number of Google News results for the story's key terms in the past day (keyless) |
| `reddit` | 0.08 | Posts linking to the story in conservative subreddits, read from each listing's public RSS (`/r/<sub>/hot/.rss`); credit decays with rank. Reddit blocks many datacenter IPs, so this often reports "unavailable" and its weight is redistributed. Set `social.reddit.rss: false` to use the JSON API instead. |
| `x` | 0.0 | Optional X API stub, off by default |

Set a weight to `0` to turn that signal off.

## `recency`
| key | default | meaning |
|---|---|---|
| `half_life_hours` | 8 | Hours for the recency score to halve |
| `max_age_hours` | 72 | Items older than this are dropped |

## `curators` / `curated`: aggregator picks (Bongino Report)

Bongino Report's own RSS feed (`/feed`) only lists its in-house clips. So Spangle reads the homepage
(`curators.bongino_report.url`, default `https://bonginoreport.com/`) and pulls out its headline links. Each one is resolved
to the **original publisher URL**; Spangle never links to bonginoreport.com. Picks that match a feed item mark that item
as curated. Other picks are added as new items under the original outlet's name (Newsmax, American Greatness, and so on).
Paywall rules still apply: paywalled domains are never linked directly, and only an existing archive snapshot can stand in.
Picks have no timestamp, so recency uses `recency.undated_curated_score`. The build log prints
`CURATOR OK Bongino Report: N original links` and `curated picks: X matched, Y added`.

| key | default | meaning |
|---|---|---|
| `curators.bongino_report.enabled` | true | Turns the source on or off |
| `curators.bongino_report.url` | https://bonginoreport.com/ | Page to read |
| `curated.saturation_curators` | 1 | Number of curators linking to a story at which the signal reaches 1.0 |
| `recency.undated_curated_score` | 0.7 | Recency score for undated curated picks |
| `weights.curated_by_aggregators` | 0.15 | Signal weight. Set it to 0 to keep the links but drop the boost. |

## `coverage`
| key | default | meaning |
|---|---|---|
| `similarity_threshold` | 0.34 | Headline similarity (IDF-weighted) needed to join a cluster. Lower merges more stories together. Higher splits them apart. |
| `saturation_outlets` | 6 | Number of outlets at which the coverage score reaches 1.0 |

### One story, one headline (event clustering)
After the headline-similarity pass, a third pass merges clusters that are the same real-world story
even when outlets word it differently (`ranking/coverage.py: event_merge`). Two clusters merge when
their founding headlines:
- name the same person (a two-word proper name seen capitalized mid-sentence somewhere, used in at most
  25 headlines, not an institution like "Supreme Court"), or one names that person by surname only; or
- share at least 3 event terms (each in at most 20 headlines) whose rarity adds up, with synonyms folded
  (probe/subpoena/raid/passport seizure count as one "investigation" term, mail/envelope = letter,
  sue/sued = lawsuit).
The page shows one headline per merged story. The outlet count is used only for ranking and is
not displayed.

## Opinion (internal only, never displayed)
The page shows no Opinion tags (Drudge-style). `ranking/opinion.py` still classifies every story so
that **the lead is always reported news**: the lead slot takes the best fresh non-opinion story (an
opinion piece leads only if no news story qualifies), and the lead's sibling-headline swap uses only
non-opinion siblings when any exist. Everywhere else, swaps prefer non-opinion siblings. Opinion can
still appear in Top Stories and the columns. A story is opinion when any of these hold:
- its feed is opinion-only, or a curator marked it (Bongino OPINION section, RCP columnists);
- its URL has an opinion section: `/opinion/`, `/commentary/`, `/columnist(s)/`, `/columns/`, `/blog/`,
  `/shows/`, `/op-ed/`, `/editorial/`, `/perspective/`, `/voices/`, `/analysis/`, `/ideas/`;
- an RSS category says Opinion, Commentary, Column(s), Columnist, Op-Ed, or Editorial;
- its outlet is mostly commentary (RedState, Hot Air, PJ Media, American Thinker, The Federalist,
  American Greatness, Townhall, Twitchy, Not the Bee, Volokh Conspiracy, Imprimis, Hollywood in Toto)
  and the URL has no news section (e.g. Townhall `/news/` counts as news);
- the headline has 2+ opinion cues: a question, first person, loaded words ("Witch Hunt", "Hoax",
  "Crazy", "Must Be Stopped", "Should"...), "Name: claim", or a "Why…/How…" opener.
The flag is kept through sibling swaps (opinion if either the original or the sibling is).

## Age limits (`age_limits`)
| key | default | meaning |
|---|---|---|
| `lead_hours` | 12 | The lead must be dated and younger than this |
| `top_hours` | 18 | Top Stories must be dated and younger than this |
| `column_hours` | 36 | Column items must be younger than this; undated items may appear only in the columns |
A sibling headline can replace a placed story only if it passes the same slot's age limit. If no story
is fresh enough for the lead, the freshest dated story leads.

## Sports / celebrity / lifestyle filter (private key `lifestyle`)
`{"terms": [...], "hooks": [...], "max_per_column": 1}`. A story whose headlines mostly match a term,
with no political hook (policy, culture-war, or government angle) to save it, never leads, never enters
Top Stories, and appears at most `max_per_column` times per column, placed low. The lexicon is private.

## GOP-negative framing (private key `framing`)
Besides the entity/negative-term window and the court rule, `subject_terms` (e.g. "faces lawsuit",
"accused of") flag a story when one of `subject_entities` is the subject, i.e. comes right before the
term ("X Faces Lawsuit"; "Trump DOJ: Y indicted" is not flagged). With `top_exclude: true`, flagged
stories stay out of the lead and Top Stories and sit low in the columns.

## Amplifier freshness (`amplifier_stale_hours`, default 6)
If the `AMPLIFIER_ITEMS` secret is missing or its newest item is older than this, the build logs a
GitHub Actions warning ("amplifier data stale") so the refresh routine can be checked.

## Tests and deploy gate
`.github/workflows/build.yml` runs `python -m unittest discover -s tests` before building and the
confidentiality guard again on the built page; any failure stops the deploy. Tests cover headline style,
shortening, ranking signals (retreat, lean, framing, lifestyle), dedup, age limits, QOTD placement and
freshness, page rendering, outlet names, and confidentiality (terms are read from the secret at run time
and never printed). Builds run at :07 and :37 each hour; a running build is queued, never cancelled.

## Quote of the Day

One public editorial feature (independent of ranking). Rendered as a **regular column item**
with the same markup as other headlines: a small red `QUOTE` kicker above the headline, the
full quote text below it, then the source line `Author · Work, locator`. The link goes to
`verification_url` when present. It is the only tag shown on the page.

| File | Apply script | Input scratch |
|---|---|---|
| `quote_of_the_day.json` | `/workspace/qotd.py apply` | `/workspace/qotd_today.json` |

Schema: `date`, `headline`, `quote`, `author`, `work`, `locator`, optional `verification_url`.
Unified verified bank: `/workspace/qotd_bank.json` (extensible `authors[]` + `quotes[]`).
Rotation: one author per day, no consecutive same author, no quote-id repeats
(`python3 /workspace/qotd.py pick`). Usage: `/workspace/quote_used.json`. Prefer ≤60 words.

Placement (in `settings.json` → `placement.quote_of_the_day`):

| key | default | meaning |
|---|---|---|
| `enabled` | true | Insert the daily quote into a column |
| `column` | 1 | 0-based column index (1 = middle of three) |
| `index` | 7 | 0-based row within that column |

Authors currently in rotation: C. S. Lewis, Thomas Sowell, Antonin Scalia, George Washington,
Ronald Reagan, Abraham Lincoln, Robert Bork (D.C. Circuit opinions, verified on OpenJurist), John Marshall (opinions, verified on Cornell LII), and Sun Tzu
(Lionel Giles 1910 translation only, Project Gutenberg #132). Only quotes checked word-for-word against the original text
(published work, opinion, speech, or column) are in rotation; quotes sourced only from Wikiquote or
AZQuotes are kept out until verified. Public mentions of these authors are limited to this quote
feature and are never tied to ranking/alignment.

**Freshness guard.** `quote_of_the_day.json` is used only if its `date` is today (UTC). Otherwise
(the daily routine did not run) the build picks a quote deterministically from `qotd_bank.json`
in the repo, which holds only primary-source-verified quotes, so a stale quote is never shown.

## Niche drop

`niche.drop: true` removes a story from the page entirely when its source is a niche source and
its title contains a `drop_terms` entry (project, symposium, series, podcast, tribal, ...) but no
`drop_hooks` entry (national hooks, stricter than `national_hooks`, so "Supreme Court" alone does
not save it). Other niche matches are only demoted.

## Lean filter (`lean_filter`)

Per-source keep rule for sources that publish both sides. `sources` maps a source name to
`"all"` (default) or `"right_only"`. `"RealClearPolitics Picks"` is the name used for RCP's aggregated links.

| key | default | meaning |
|---|---|---|
| `sources` | RCP + RCP Picks `right_only`, First Things `all` | Per-source mode |
| `threshold` | 1 | Minimum lean score to keep a `right_only` item |
| `outlet_weight` / `author_weight` | 2 / 2 | Score for a right (+) or left (−) outlet or author |
| `right_outlets` | generic list | Outlets treated as right-leaning |
| `left_outlets`, `right_terms`, `left_terms`, `right_authors`, `left_authors` | empty | Public defaults are generic. Real lists are merged from the private config. |

Score = outlet lean + author lean + one point per right term − one per left term, matched on the title and description.
Feed logs print `LEAN <source>: kept N, filtered M`.

## RealClearPolitics

- **Own commentary:** `realclearpolitics.com/articles/index.xml` is a feed, filtered by `lean_filter`.
- **Picks (curator `realclearpolitics`):** `index.xml` and the feedburner RSS. Each pick resolves to its
  `<originalLink>`. Walled or blocked domains (`PAYWALL_DOMAINS` + `skip_domains`) are skipped,
  and the lean filter is applied. Kept picks count toward `curated_by_aggregators`.
- **Curator weights:** `curated.weights` (`{"Bongino Report": 1.0, "RealClearPolitics": 0.7}`).
- **Polling news:** right-favorable poll headlines (for example "GOP leads") score as right through the lexicon.

## Headlines: style manual, overrides, rewrites

See [STYLE.md](STYLE.md) for the living Drudge-style guide.

- **`headline_style.json`:** machine-applicable rules (abbreviation replacements, banned filler,
  trailing-tag stripping, max length). Applied deterministically to every displayed headline on every build.
- **`headline_overrides.json`:** `{ "https://…/article": "Punchy Display Headline" }`. Wins over the
  original (and over style cleanup). Public and fine to commit; it's just display text. The original
  stays in the link's `title` attribute.
- **Cluster sibling pick:** after placement, if the chosen outlet's headline is bland but another
  free outlet in the same story-cluster has a punchier non-bland headline, Spangle displays (and links
  to) that sibling instead. Only when *every* candidate is bland is the story queued for a rewrite.
- **Box rewriter (hourly):** `/workspace/rewrite_queue.py` builds the site locally and writes
  `/workspace/rewrite_queue.json`. The parent agent writes punchy replacements to
  `/workspace/rewrites_done.json`, then runs `python3 /workspace/rewrite_queue.py apply` to commit
  them as `headline_overrides.json` and trigger the workflow.

## Niche demotion (`niche`)

Scholarly / inside-baseball / literary posts from configured sources (Volokh, SCOTUSblog, Cato, Heritage, AEI,
First Things by default; poetry, fiction, book reviews and niche theology terms are included) are demoted unless the headline also hits a national hook. Tunable in `settings.json`:

| key | default | meaning |
|---|---|---|
| `enabled` | true | |
| `demotion` | 0.4 | Score (0–1) when flagged; 1.0 means no demotion |
| `sources` | Volokh, SCOTUSblog, Cato, Heritage, AEI | |
| `terms` | symposium, law review, book review, short circuit, jurisprudential, … | Triggers the demotion |
| `national_hooks` | SCOTUS, ruling, nominee, Trump, border, … | Saves the story from demotion |
| `weights.niche` | 0.08 | Ranking weight |

## `lead`: lead eligibility (`ranking/lead.py`)

The lead slot needs a story that passes a **hard topic gate**, meets the **national-significance** minimums (enough outlets, at least one major outlet, a national topic, and a score of at least `sig_min`), and has a **lead signal** at or above `threshold`.
The lead signal is a lexicon match on the headline, either a "win" (a win term plus an entity, or an opponent-loss phrase)
or an "outrage" term, with a boost for intensity words. It's averaged across the cluster's headlines, so one stray headline
can't qualify a story. Eligible stories are ranked by `weights` (signal, coverage, amplifiers, alignment, original rank) among
the top `candidates` clusters. If none qualify, the most significant eligible political story becomes the lead. The **soft gate**, which also includes the hard gate, keeps gated stories out of the Top Stories block; they can still appear in the columns.

| key | default | meaning |
|---|---|---|
| `enabled` | true | Turns lead eligibility on or off |
| `threshold` | 0.4 | Minimum lead signal (0–1) |
| `candidates` | 80 | Number of top-ranked clusters considered |
| `weights` | signal 0.45, coverage 0.2, amplifiers 0.1, alignment 0.15, rank 0.1 | Lead score mix |
| `gate_paths` / `gate_categories` / `gate_keywords` | sports, golf, entertainment, lifestyle, weather, obituaries and similar | Hard gate, applied to URL paths, feed categories or curator sections, and headline words |
| `soft_gate_paths` / `soft_gate_categories` | business, markets, science, tech | Extra exclusions for Top Stories only |
| `political_terms` | generic politics words | Used by the fallback |
| `sig_min` | 0.45 | Minimum national-significance score (0–1) a lead must have |
| `sig_min_outlets` | 3 | Minimum number of distinct outlets in the story's cluster |
| `sig_major_tier` / `sig_major_outlets` | 0.8 / [] | At least one outlet must have a tier at or above this, or be named in the list |
| `sig_weights` | coverage 0.5, national 0.35, amplifiers 0.15 | Significance mix. Coverage is scaled up to `sig_coverage_saturation` (6) outlets, national is the number of `national_terms` hits across the cluster's headlines (2 hits = full), and amplifiers counts any amplifier match. |
| `national_terms` | Congress, Senate, Supreme Court, White House, DOJ, FBI, Pentagon, elections, border, economy, war, China, Iran, Russia and similar | National-importance topics. At least one hit is required. |
| `demote_terms` / `sig_demotion` | celebrity, brand, local and similar / 0.3 | Penalty for local, celebrity or consumer stories |
| `sig_single_source_demotion` | 0.2 | Penalty for single-outlet stories |
| `weights.significance` | 0.0 | How much significance counts in the lead score (raise it in the private config) |
| `win_terms`, `win_entities`, `opponent_loss_terms`, `outrage_terms`, `intensity_terms` | small generic lists | Lexicons |

The private config can override any of these keys under `"lead"` (see the schema below). The build log prints
`lead: N eligible candidates above threshold`, or a fallback notice.

## Paywalls and registration walls

These rules apply to every item, whether it comes from a feed, a curated pick or a cluster. They're defined in `aggregator.py`.

- **`PAYWALL_DOMAINS`:** domains, including all their subdomains, that are never linked directly. Their stories still count toward
  cross-outlet coverage, and they can appear only through an existing archive snapshot (see `archive`). Besides the hard paywalls
  (WSJ, NYT, WaPo, Bloomberg, FT, The Atlantic and others), the October 2026 audit added these registration, meter or premium walls:
  theepochtimes.com, telegraph.co.uk, newsweek.com, spectator.co.uk, thespectator.com, spectator.com.au, dailycaller.com.
- **`WALL_PATTERNS`:** each chosen link is fetched (when `placement.check_links` is on) and dropped if its HTML contains a
  specific wall marker. Examples are the schema.org `isAccessibleForFree: false` flag, "subscribe to continue reading", "create a free account to
  continue", "sign in to keep reading", "you have reached your article limit", Blaze Media's `topic-premium`, National Review Plus and
  Substack paid posts. A link is also dropped if it redirects onto a blocked domain.
- Generic words like "subscribe", "paywall" or the Piano, Tinypass and Zephr scripts aren't used, because many free sites load them
  (Hot Air, Townhall, PJ Media, SCOTUSblog and the Washington Examiner all do) and they would cause false positives.
- Pinned links on a blocked domain are skipped unless they include `archive_url`.
- Dropped links are logged as `link dropped (wall marker ...)`.

To block another domain, add it to `PAYWALL_DOMAINS` and commit. To catch a new per-article wall, add a specific phrase to `WALL_PATTERNS`.

## Feeds

Public feeds are listed in `FEEDS` in `aggregator.py`. Additional feeds can come from the private config key `private_feeds` (`[{"name", "url", "opinion", "ua": "feed"|"browser", "options": {...}}]`); their names never appear in the repo and their log lines read `private feed #n`. Their source tiers go in the private key `source_tiers` (merged over `sources.tiers` at build time). A feed can carry options: `byline` keeps only items whose author contains that text, `max_age_hours` overrides `recency.max_age_hours` (placement still applies the column age limit), and `substack_free_only` checks each Substack post through Substack's public post API and skips paid-only posts.

Feeds added Oct 2026: **Judicial Watch** (`judicialwatch.org/feed/`, press releases and blog; tier 0.8) and **O’Keefe Media Group** (tier 0.7). OMG has RSS turned off, so it is read from its public WordPress REST API (`format: "wp_json"`); posts in the paid "full-access" category (`exclude_categories: [210]`) are skipped, and the feed uses the feed-reader user agent because the site returns 403 to browser-like agents. Its posts are infrequent, so `max_age_hours` is 168 (the 36-hour column limit still applies at placement). Substack and Rumble were not used: the Substack feed is empty and Rumble has no feed.

**Imprimis** (Hillsdale, `imprimis.hillsdale.edu/feed/`, tier 0.8, tagged Opinion) is monthly, so it has its own freshness window via feed options: `max_age_hours`/`column_age_hours` 840 (35 days: the current or most recent issue only; older archive pieces are excluded), `no_front` (never the lead or a Top Story), and `reserved_slot` (its freshest eligible piece always gets one column slot, replacing the lowest-ranked column item if the columns are full). A single-outlet monthly piece would otherwise never outrank same-day news. Any feed can use these options.

## `sources`
| key | default | meaning |
|---|---|---|
| `default_tier` | 0.5 | Tier for any feed not listed |
| `tiers` | per outlet, 0.5–0.9 (legal analysis rated high: SCOTUSblog 0.9, Volokh Conspiracy 0.85; think tanks Cato Institute 0.85, Heritage Foundation 0.85, AEI 0.85, Courthouse News 0.85; Not the Bee 0.5, since it's satirical commentary) | Source weight (0–1). It also decides which outlet's link represents a cluster. |

## `social`
| key | default | meaning |
|---|---|---|
| `candidates` | 40 | How many top clusters get social lookups |
| `timeout_seconds` | 10 | Per-request timeout |
| `google_news.enabled` / `saturation` | true / 40 | Result count that maps to roughly 0.75 |
| `reddit.enabled` | true | |
| `reddit.subreddits` | Conservative, conservatives, Republican, ConservativeNews | Subreddits checked (hot and new) |
| `reddit.saturation` | 1500 | Score + 2×comments that maps to roughly 0.75 |
| `hackernews.enabled` / `saturation` | true / 200 | |
| `x.enabled` | false | Also needs an `X_BEARER_TOKEN` repo secret, plus `X_BEARER_TOKEN: ${{ secrets.X_BEARER_TOKEN }}` added to the workflow's Build step `env` (it isn't wired in by default) |
| `x.max_requests` | 20 | Hard cap on X API calls per run. X API pricing is pay-per-use, about $0.005 per counts request. |
| `x.saturation` | 500 | Post count that maps to roughly 0.75 |

## `placement`
| key | default | meaning |
|---|---|---|
| `top_stories` | 5 | Items in the Top Stories block below the lead |
| `column_items` | 45 | Items spread across the columns |
| `columns` | 3 | Number of columns |
| `max_per_outlet_top` | 1 | Maximum items per outlet in the lead and Top Stories |
| `max_per_outlet_total` | 5 | Maximum items per outlet on the whole page |
| `lead_respects_exclusions` | true | Keeps clusters flagged by the framing signal out of the lead slot |
| `check_links` | true | Checks each chosen link for a 200 response with no paywall marker |

## `archive`: archive fallback for paywalled originals (on by default)

Paywalled domains are never linked directly. When this feature is on, WSJ and NYT feeds are fetched as well, but only so they
count toward cross-outlet coverage and can serve as the "original" of a story. For a cluster with at least
`min_outlets` outlets where the earliest item is paywalled (or where every item is paywalled), Spangle looks for an
**existing** snapshot of that article. It never submits new captures. If a snapshot is found, the archived copy is linked
and marked "archived copy". If not, the best free link is used, or the story is dropped when no free link exists.

| key | default | meaning |
|---|---|---|
| `enabled` | true | Master switch. When false, paywalled feeds aren't fetched at all. |
| `min_outlets` | 3 | Minimum distinct outlets in a cluster before an archive lookup is tried |
| `providers` | ["archive_today", "wayback"] | Lookup order. `archive_today` uses `GET archive.ph/newest/<url>` and reads the redirect only. `wayback` uses `archive.org/wayback/available`. |
| `timeout_seconds` | 6 | Per-lookup timeout. CAPTCHA pages, blocks and timeouts count as "not found". |
| `max_lookups` | 12 | Cap on lookups per run |
| `ingest_paywalled_feeds` | true | Whether to fetch the WSJ and NYT feeds |

The build log prints `archive lookups (found/tried)` for each provider.

## `manual_links`: hand-picked pins

| key | default | meaning |
|---|---|---|
| `enabled` | true | |
| `file` | manual_links.json | Path to the pins file |

Edit `manual_links.json` on GitHub and commit (or run the workflow by hand). Example:

```json
{"links": [
  {"title": "Headline text", "url": "https://example.com/story",
   "archive_url": "https://archive.ph/XXXX", "position": "lead",
   "source": "Example News", "opinion": false, "expires": "2026-10-20T00:00:00Z"}
]}
```

- `position` is `lead`, `top` or `column` (default `top`).
- If `archive_url` is set, that link is shown instead of `url`.
- Pins past their `expires` time are ignored.
- Pinned items skip the link check.

## Private alignment config (Actions secret)

The `alignment` signal reads JSON from the `ALIGNMENT_CONFIG` repository secret. The build log never prints it.
Without it, generic defaults are used. To update it from the maintainer's machine:

```
gh secret set ALIGNMENT_CONFIG -R cs-514/spangle < /path/to/alignment_config.json
gh secret set AMPLIFIER_ITEMS -R cs-514/spangle < /path/to/amplifier_items.json
```

Schema (all keys optional):

```json
{
  "boost_keywords":  {"some phrase": 3},
  "demote_keywords": {"some phrase": -5},
  "authors":         {"Author Name": 8},
  "sources":         {"Outlet Name": 2},
  "lead_topics":     ["phrase"],
  "lead_topic_bonus": 4,
  "scale": 8,
  "signal_weights":  {"amplifiers": 0.15, "framing": 0.15},
  "amplifiers": [{"name": "label", "url": "https://example.com/feed.rss", "weight": 1.0, "max_age_hours": 48}],
  "amplifier_items_weight": 1.0,
  "amplifier_items_max_age_hours": 48,
  "outrage": {"terms": ["..."], "intensity": ["..."], "scale": 2.5},
  "retreat": {"actors": ["..."], "verbs": ["rules out","walks back"], "demotion": 0.3, "lead_exclude": true},
  "lead": {"threshold": 0.4, "win_terms": ["..."], "win_entities": ["..."], "outrage_terms": ["..."], "intensity_terms": ["..."]},
  "framing": {"entities": ["entity"], "negative_terms": ["term"], "window_words": 6, "lead_exclude": true,
              "court": {"actors": ["court"], "actions": ["blocks"]}}
}
```

- **Keywords:** each matching phrase in the title, summary or categories adds its weight. A match in the title counts double.
- **`authors`:** matched against the feed's author field.
- **`sources`:** matched against the feed name.
- **`lead_topics`:** a phrase in the title adds `lead_topic_bonus`.
- **`signal_weights`:** overrides the public `weights` for any signal.
- **`amplifiers`:** public RSS feeds. A story whose URL a feed links to gets full credit; strong headline-term overlap gets half. Feeds that fail are skipped and logged only as `amplifier feed N`.
- **`amplifier_items_weight` / `amplifier_items_max_age_hours`:** optional boost for posts supplied via the private `AMPLIFIER_ITEMS` Actions secret (JSON `[{"url","text","ts","weight"}]`; `weight` is optional per item, and items with the same weight are grouped as one source). Same match rules as RSS amplifiers; logged as `amplifier items`.
- **`outrage`:** term + intensity lists that boost stories. Weight via `signal_weights.outrage`.
- **`retreat`:** actors + verbs for "backing down" headlines. Flagged stories get the demotion score (default 0.3) and, with `lead_exclude`, are kept out of the lead.
- **`framing`:** a negative term within `window_words` of an entity, or a court actor plus an adverse action plus an entity anywhere in the headline, lowers the score. With `lead_exclude`, those stories are also kept out of the lead.
- **`scale`:** the raw sum is squashed to 0–1 with `0.5 + 0.5*tanh(raw/scale)`. A larger scale gives a softer effect.

## Faction signal (`ranking/faction.py`)
Private config key `faction` holds a list of in-party figures (`members`, easy to extend: add a surname
or full name) and term lists (`favorable_terms`, `defect_terms`, `critic_terms`, `attack_terms`).
Headlines that cast a member favorably or as the protagonist are downranked and kept out of the lead and
Top Stories; a member breaking ranks or obstructing the agenda is treated as outrage/betrayal material and
sibling headlines (and queued rewrites) that feature the opposing side are preferred; criticism of a
member or a primary challenge is boosted. Weight: `signal_weights.faction` (private). The list is never
in the repo; the confidentiality guard checks for it.

## Minor-figure rule (`ranking/minor.py`, settings `minor_figures`)
A statement or position from a minor figure (non-presidential candidate, state legislator, backbench
House member, local official, commentator) is not national news by itself: strongly downranked and kept
out of the lead and Top Stories. Exceptions: a nationally prominent speaker (generic office-based list in
the module, extendable via `minor_figures.prominent`), real action (vote, ruling, bill, arrest,
indictment), wide coverage (`min_outlets`, default 5, including a major outlet), and scandals in a watched
race (columns allowed, never the lead). `suppress_urls` (settings) removes individual stories; entries may
be `sha256:` URL keys.

## Defeatism rule (`ranking/defeatism.py`)
Private config key `defeatism` (lexicons not in the repo). Headlines asserting that one configured side
can't win, is doomed or will lose are excluded from the page entirely; the same framing about the other
configured side is boosted. Headline overrides and rewrites can never introduce that framing: the build
reverts such a display to the original title, and the box-side rewrite tool rejects it.

## Clean pages (`ranking/clutter.py`, `clutter_scores.json`, `scripts/clutter_refresh.py`)
`scripts/clutter_refresh.py` fetches a recent article from each public feed and scores the outlet's
page cleanliness (0–1, 1 = clean): page weight, `<script>` count, known ad/tracker hosts, autoplay
video, newsletter/interstitial/paywall modal markers, and text-to-HTML ratio. Results (and any tested
lighter URL variant) go to the public `clutter_scores.json`; rerun the script to refresh.
- **Signal `clutter`** (weight 0.05 in settings): the cleanest item in the cluster; unknown domains 0.5.
- **Clean links** (settings `clean_links`): after the headline is chosen, the story links the
  sibling with the best `0.45·tier + 0.40·cleanliness + 0.15·freshness` if it beats the current link by
  `min_gain`. Siblings must pass the slot's age limit, not be paywalled or truncated, and, for the lead,
  be non-opinion. Hand-written overrides, quotes and archived links never change.
- **Lighter variants**: for outlets whose AMP / `?outputType=amp` / `/amp/` page was verified to carry the
  full article without a login, the build fetches both pages and uses the variant only if it returns
  200, has no subscribe/login wall and at least 80% of the canonical article text; otherwise the
  canonical URL stays.
