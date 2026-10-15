# Rampart Report

A conservative news aggregator in the classic one-page, link-list style. Updated hourly.

- Pulls public RSS/Atom feeds from free-to-read conservative-leaning news and opinion outlets.
- Free links only: paywalled domains are blocklisted and article links get a light availability/paywall check.
- Every headline links straight to the original publisher.
- Built by a GitHub Actions workflow every hour and published to GitHub Pages.

## Run locally

```
python3 aggregator.py   # writes site/index.html (Python 3.10+, stdlib only)
```

Optional: set `ALIGNMENT_CONFIG` to a JSON object to tune ranking weights
(`boost_keywords`, `demote_keywords`, `authors`, `sources`, `lead_topics`,
`recency_half_life_hours`). Sensible defaults are used when it is unset.
