# Spangle upkeep: how the site runs itself

Everything runs on GitHub Actions in this repo. No other computer is needed. You can change any of it from
a coding tool by editing files and pushing to `main`.

## The pieces

| Workflow (`.github/workflows/`) | When (US Eastern) | What it does |
|---|---|---|
| `build.yml` **Build and deploy** | about every 30 min (GitHub often runs it late) | Unit tests, fetch the feeds, rank, write `site/index.html`, confidentiality check, publish to GitHub Pages. |
| `upkeep.yml` **Upkeep** | about 7 AM and 4 PM | 1. Refreshes the private amplifier items (`upkeep/amplifiers.py`). 2. Headline rewrites with an LLM (`upkeep/rewrite.py`). 3. Health check (`upkeep/health.py`). |
| `qotd.yml` **Quote of the Day** | about 1:10 AM | Picks one unused, verified quote from `qotd_bank.json` and commits `quote_of_the_day.json` (`upkeep/qotd.py`). |
| `watchdog.yml` **Watchdog** | every hour at :23 | Health check only: if the live page is more than 90 min old or the last build failed, it starts a build. If the site stays down (3 hours, or 3 failed builds) it opens a `site-outage` issue (GitHub emails you) and closes it when the site recovers. |

Start any of them by hand: **Actions** tab → pick the workflow → **Run workflow**, or
`gh workflow run upkeep.yml`. A manual run skips the time-of-day check.

**Time zones.** GitHub schedules in UTC only. Each Eastern-time job is scheduled at both possible UTC hours
(daylight and standard time), and `upkeep/slot.py` lets through only the run that lands in the Eastern window
and hasn't run yet that day (stamps in `upkeep/state/slots.json`). Nothing to change at daylight-saving time.

**No push races.** Upkeep and QOTD share the concurrency group `spangle-upkeep`, so they never push at the same
time; pushes also rebase and retry. The build only reads the repo, and the upkeep jobs start a new build after
they commit.

## Files

| Path | What it is |
|---|---|
| `aggregator.py`, `ranking/`, `settings.json` | The site builder and ranking engine (see `docs/CONTROLS.md`). |
| `headline_overrides.json` | `{article URL: display headline}`. Written by the rewrite job; you can edit it by hand. |
| `qotd_bank.json` | The verified quote bank (exact text, source link, `impact` 1-5). |
| `quote_of_the_day.json` | Today's quote (written by the QOTD job). |
| `upkeep/` | The upkeep jobs. `upkeep/state/` holds their public state (quote usage, slot stamps). |
| `docs/STYLE.md` | Headline style manual (the LLM gets it in full). |

## Secrets (Settings → Secrets and variables → Actions)

Names only; the values are private. Jobs that are missing an optional secret still succeed and log a
warning ("degraded mode").

| Secret | Needed for | If missing |
|---|---|---|
| `ALIGNMENT_CONFIG` | Ranking, confidentiality guard (required) | Build runs unranked and the guard is skipped. Rewrite job refuses to commit. |
| `AMPLIFIER_ITEMS` | Ranking signal read by the build | No amplifier boost. |
| `AMPLIFIER_SOURCES` | Which outside accounts the amplifier refresh reads (private) | Amplifier refresh is skipped. |
| `ENGAGEMENT_DATA` | Old engagement signal (no longer refreshed; ignored when stale) | Nothing. |
| `LLM_API_KEY` | Headline rewrites and the QOTD pick | No rewrites; QOTD is picked by the rotation rules alone. |
| `LLM_BASE_URL` (optional, secret or variable) | Any OpenAI-compatible API. Default `https://api.openai.com/v1`. Anthropic: `https://api.anthropic.com/v1`. | Default used. |
| `LLM_MODEL` (optional, secret or variable) | Model name, e.g. `gpt-4o-mini` or a Claude model id | `gpt-4o-mini`. |
| `REWRITE_GUIDANCE` (optional) | Extra private rewrite guidance sent to the LLM | Public guidance only. |
| `X_BEARER_TOKEN` (optional) | X API reads for the amplifier refresh (pay per use) | That feed keeps its previous items. |
| `SECRETS_PAT` (optional) | Writing the refreshed `AMPLIFIER_ITEMS` secret back (the built-in token cannot write secrets). Fine-grained token, this repo only, permission "Secrets: Read and write". | Refresh runs but the build keeps the old `AMPLIFIER_ITEMS`. |

Some outside sources block GitHub's servers (HTTP 403). The refresh then keeps that feed's previous items
until they age out; the build is unaffected.

## Run locally

```
python3 aggregator.py                                 # build site/index.html (Python 3.10+, stdlib only)
python3 -m unittest discover -s tests                 # all tests
python3 -m upkeep.qotd --dry-run                      # show today's quote pick
python3 -m upkeep.rewrite --queue                     # show how many headlines need a rewrite
python3 -m upkeep.health                              # check the live site
```

Set the secrets as environment variables to use them locally (for example `export LLM_API_KEY=...`).
Local runs never commit unless `UPKEEP_PUSH=1` is set.

## Rules the jobs (and you) must follow

- **Confidentiality.** The repo, its commits, docs, tests and Actions logs are public. The private ranking
  configuration (people, account lists, term lists, private feeds) lives only in secrets. Never paste a
  value from a secret into code, docs, tests, commit messages or logs, and never print one: log counts. The
  test `tests/test_confidentiality.py` fails the build if a private term shows up in a tracked file or the page;
  run it with the secret loaded before pushing. Do not upload private data as artifacts or caches (both are
  readable by others on a public repo), and never use `pull_request_target` with secrets.
- **Free links only.** No paywalled or limited-access links.
- **Headlines** follow `docs/STYLE.md`: at most about 10 words, faithful to the article, complete thoughts,
  balanced curly quotes, AP/Chicago title case, closed em dashes, only well-known acronyms, no source lines
  under headlines.
- **What runs:** no sports, devotional or celebrity stories without a political hook; routine crime needs a
  national hook; satire is never the lead or a Top Story (it may run in the columns).
- **Quote of the Day:** exact verified text from primary sources only, never the same author two days
  running, favor famous high-impact lines, and pick authors de-weighted in the bank's `author_weights` less often. No per-quote headline: the page shows the small red
  QUOTE OF THE DAY label, the quote in italics, and the attribution linked to its source. To add quotes, add
  bank entries with `verified: true`, `source_type: "primary"` and a `verification_url` to the primary text.

## Costs (estimates, November 2026)

- GitHub Actions minutes: free (public repo).
- LLM: about 15K tokens in and 1K out per upkeep run, two runs a day, plus a tiny QOTD call: under $1/month
  with a small model (e.g. gpt-4o-mini class), about $3-6/month with a frontier model.
- X API (only if `X_BEARER_TOKEN` is set): pay per use, about $0.005 per post read; at about 25 posts per run,
  two runs a day, roughly $5-10/month.
