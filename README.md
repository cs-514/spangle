# Spangle

A conservative news aggregator in the classic one-page, text-link style. Updated hourly.

- Pulls public RSS/Atom feeds from free-to-read conservative-leaning news and opinion outlets.
- Free links only: paywalled domains are blocklisted, and each chosen link gets a light availability and paywall check.
- Every headline links straight to the original publisher.
- Stories are clustered across outlets and ranked by a modular engine (`ranking/`) with weights in `settings.json`.
  See [docs/CONTROLS.md](docs/CONTROLS.md).
- Built by GitHub Actions every hour and published to GitHub Pages.

## Run locally

```
python3 aggregator.py   # writes site/index.html (Python 3.10+, stdlib only)
```

## Typography notes

The design borrows newspaper techniques, not fonts: a high-contrast display serif for the lead
(Playfair Display, standing in for NYT Cheltenham and WSJ Escrow display), a readable text serif
for headlines (Source Serif 4, in the role of NYT Imperial and WSJ Exchange), and a grotesque sans for labels
and metadata (Libre Franklin, a free revival of Franklin Gothic, which NYT uses for labels and WSJ's
Retina fills). Other borrowed techniques: tracked small-caps sans section labels over a hairline rule, thin
rules between items, a double rule under the masthead, roughly 19–22px headline sizes with 1.2–1.3 line-height, a
constrained measure for the lead (about 22ch), near-black ink on white, and a 3 → 2 → 1 column grid as the screen narrows.

## Headline style

See [docs/STYLE.md](docs/STYLE.md). Display overrides live in `headline_overrides.json`.

A daily C. S. Lewis quotation appears under the lead when `quote_of_the_day.json` is set.
