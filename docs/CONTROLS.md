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
| `reddit` | 0.08 | Score and comments on posts linking to the story in conservative subreddits (keyless) |
| `hackernews` | 0.04 | HN points and comments for the URL (keyless; rarely fires on political news) |
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

Feeds are listed in `FEEDS` in `aggregator.py`. A feed can carry options: `byline` keeps only items whose author contains that text (used for AEI's search feed filtered to one author), and `max_age_hours` overrides `recency.max_age_hours` for infrequent writers (the AEI author feed uses 336, which is 14 days). `substack_free_only` checks each Substack post through Substack's public post API and skips paid-only posts (used for private feed's Substack, which is treated as opinion).

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
| `opinion_tag` | true | Shows a small "Opinion" tag, but only for opinion-only feeds (Fox News Opinion, NY Post Opinion, Volokh Conspiracy, Cato op-eds and blog, private feed, Not the Bee) or `/opinion/` and `/commentary/` URLs, which catches Heritage commentary. Heritage reports and SCOTUSblog are treated as news. |
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
- **`amplifier_items_weight` / `amplifier_items_max_age_hours`:** optional boost for posts supplied via the private `AMPLIFIER_ITEMS` Actions secret (JSON `[{"url","text","ts"}]`). Same match rules as RSS amplifiers; logged as `amplifier items`.
- **`framing`:** a negative term within `window_words` of an entity, or a court actor plus an adverse action plus an entity anywhere in the headline, lowers the score. With `lead_exclude`, those stories are also kept out of the lead.
- **`scale`:** the raw sum is squashed to 0–1 with `0.5 + 0.5*tanh(raw/scale)`. A larger scale gives a softer effect.
