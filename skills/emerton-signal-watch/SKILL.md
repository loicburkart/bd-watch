---
name: emerton-signal-watch
description: Capture and qualify Emerton business-development signals — scrape French executive nominations and sector press (Google News RSS), then score each signal against Emerton's 3D targeting matrix (sector × geography × function) and return the qualified ones (P1/P2/P3) as structured data. This is the watch + qualify stage of the bd-watch BD pipeline: it answers "who should we reach out to right now, and why", but does not find contacts or draft messages. No LLM, no API key — the only network call is the RSS fetch. Use whenever someone wants a fresh, scored watchlist of prospects to act on. Triggers: "find BD signals", "qui contacter cette semaine", "scrape nominations", "signaux qualifiés", "refresh the watchlist".
---

# Emerton Signal Watch

The **watch + qualify** step of Emerton's BD pipeline (`watch → qualify → contact → draft → review`).
It scrapes recent executive **nominations** and **sector press** (Google News RSS), converts each
hit into a structured signal, and scores it against Emerton's **3D targeting matrix**
(sector × geography × function). The output is the list of **qualified** signals — the reasons to
reach out — ranked by priority. It does **not** identify contacts or write messages; those are the
downstream skills.

Runs as plain Python (`feedparser` + `pyyaml`); no LLM, no API key, no server.

## When to use

The user wants a fresh, scored watchlist of prospects — e.g. *"find this week's BD signals"*,
*"qui contacter en agroalimentaire en France"*, *"refresh the watchlist"*. Stop after presenting the
qualified signals; hand off to `emerton-message-drafter` for the actual outreach.

## Setup

From the skill's `scripts/` directory, install the two runtime deps once:

```bash
cd scripts
python -m pip install -q feedparser pyyaml
```

The config files (`targeting_matrix.json`, `triggers_module/targeting_config.yaml`) live at the
**skill root** (one level above `scripts/`) and are resolved automatically by the package — do not
move them.

## Workflow

1. **Run the watcher** from `scripts/` and read the JSON:

   ```bash
   python run_signals.py            # JSON: {"count": N, "signals": [...]}
   python run_signals.py --format text   # human-readable, P1-first
   ```

   Options:
   - `RSS_LOOKBACK_HOURS=720 python run_signals.py` — narrow the window (default 1440h ≈ 60 days).
   - `python run_signals.py --threshold 0.3` — lower the bar to include P3 signals (default 0.5).

2. **Present the qualified signals** to the user, ranked by `score` (P1 = 1.0 ★, P2 = 0.6, P3 = 0.3).
   For each: company, the one-line `summary`, `sector` / `geography` / `contact_function`, the score,
   and the `source_url`. Group or sort by score so the strongest reasons surface first.

3. **If `count` is 0**, say no qualifying signal was found in the window and offer to widen it
   (`RSS_LOOKBACK_HOURS` larger, or `--threshold 0.3`). **Never invent a signal.**

## Output (per signal)

```json
{
  "company": "…",
  "summary": "…",                 // the nomination / press headline
  "type": "new_appointment",      // new_appointment | funding_round | press_article | …
  "sector": "food",               // canonical matrix value
  "geography": "france",
  "contact_function": "supply_chain",
  "salience": "high",
  "date": "2026-06-27",
  "source_url": "https://…",
  "score": 1.0,                   // 1.0 = P1, 0.6 = P2, 0.3 = P3
  "reason": "sector=food(1.0) geo=france(1.0) func=supply_chain(1.0)"
}
```

## Scoring rule

Global score = `min(sector, geo, function)` across the three axes — **except** a P1 sector (food /
agroalimentaire / FMCG) always scores 1.0 (core sector is always relevant). A signal is kept when its
score ≥ threshold (0.5 by default, i.e. P2 or better). The matrix is config-driven
(`targeting_matrix.json`); edit it to retune priorities — no code change needed.

## Notes

- Scope: modules 01 (watch) + 02 (qualify) only. Contact discovery and message drafting are separate
  skills — do not fold them in here.
- MergerMarket (Playwright) is intentionally excluded to keep the skill light; sources are Google-News
  RSS nominations + press.
- The RSS step needs internet access. If a feed fails, report the stderr warning rather than presenting
  a silent fallback as a real signal.
