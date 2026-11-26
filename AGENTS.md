# Instructions for AI coding tools working on Spangle

Spangle is a one-page, Drudge-style conservative news aggregator built by GitHub Actions and published on
GitHub Pages. Read `docs/UPKEEP.md` (how it runs), `docs/STYLE.md` (headline style) and `docs/CONTROLS.md`
(ranking knobs) before changing anything.

## Hard rules

1. **Confidentiality (most important).** This repo is public. The private ranking configuration, including
   any people, accounts, outlets lists, term lists, feeds or weights, lives only in GitHub secrets
   (`ALIGNMENT_CONFIG`, `AMPLIFIER_SOURCES`, `AMPLIFIER_ITEMS`, `REWRITE_GUIDANCE`). Never write their
   contents, or guesses at them, into code, comments, tests, docs, commit messages, issues or logs. Code reads
   them from environment variables and logs counts only. Use generic placeholders in tests. Never add a
   workflow step that prints a secret, uploads private data as an artifact or cache, or uses
   `pull_request_target`.
2. **Run the tests before every push:** `python3 -m unittest discover -s tests`. With the secrets loaded
   (`ALIGNMENT_CONFIG`, and `AMPLIFIER_SOURCES` if you have it) the confidentiality guard
   `tests/test_confidentiality.py` must pass, not skip.
3. **Free links only:** never add paywalled or limited-access sources.
4. **Headlines** (`docs/STYLE.md`): about 10 words max, faithful to the article, complete thoughts with a
   finite verb, curly quotes, title case, closed em dashes, only well-known acronyms. Never defeatist
   framing about the right; feature the opponent or the action. No source lines under headlines.
5. **Placement:** satire is never the lead or a Top Story (columns are fine). Drop sports, devotional and
   celebrity stories without a political hook; routine crime needs a national hook.
6. **Quote of the Day:** only exact, primary-source-verified text from `qotd_bank.json`; rotate authors; no
   per-quote headline.
7. Python standard library only (no pip dependencies) unless there is a strong reason.
8. Keep `upkeep/state/` and `headline_overrides.json` valid JSON: the jobs commit to them.
