# emerton-signal-watch — Claude Skill

The **watch + qualify** step of the `bd-watch` BD pipeline, packaged as a standalone Claude Skill.
It scrapes recent French **executive nominations** and **sector press** (Google News RSS), turns each
hit into a structured signal, and scores it against Emerton's **3D targeting matrix**
(sector × geography × function). The output is a ranked list of **qualified signals** — the reasons to
reach out — that you hand off to the contact/drafting skills.

It runs as plain Python (`feedparser` + `pyyaml`) — **no LLM, no API key, no server**. The only
network call is the RSS fetch.

---

## What it does

1. Scrapes nomination + press feeds (Google News RSS) via the bundled `bd_watch` scrapers.
2. Converts each hit into a `Trigger` (company, sector, geography, contact function, …).
3. Scores it against the 3D matrix: global score = `min(sector, geo, function)`, with a P1 sector
   (food / agroalimentaire / FMCG) always scoring 1.0.
4. Keeps signals at or above the threshold (0.5 by default → P2 or better) and prints them.

It is the **watch → qualify** stage only. It does **not** find contacts or write messages.

---

## Installation

The skill ships as a single `.skill` file (a zip with the folder as its root).

**Install (per person):**
1. In Claude desktop / Cowork: **Customize → Skills → "+"** and upload `emerton-signal-watch.skill`.
   Uploaded skills are private to your account.

**Rebuild the `.skill` after editing the source:**
```bash
cd bd-watch/skills
zip -r emerton-signal-watch.skill emerton-signal-watch -x '*/__pycache__/*' '*.pyc'
```

**Refresh the bundled engine from the live repo** (after the `bd_watch` package, matrix or
scraper config change on `main`), run from the repo root:
```bash
skills/emerton-signal-watch/build.sh
```
It re-copies the minimal package + config from `src/` and re-zips the `.skill`.

(Docs: https://support.claude.com/en/articles/12512198-how-to-create-custom-skills)

---

## Usage

In a Claude / Cowork chat, say something like *"Find this week's BD signals"* or
*"qui contacter en agroalimentaire en France"*. Claude will:

```bash
cd scripts
python -m pip install -q feedparser pyyaml
python run_signals.py            # JSON: {"count": N, "signals": [...]}
python run_signals.py --format text   # human-readable, P1-first
```

Options:
- `RSS_LOOKBACK_HOURS=720 python run_signals.py` — narrow the window (default ≈ 60 days).
- `python run_signals.py --threshold 0.3` — include P3 signals (default keeps P2+).

It then presents the qualified signals ranked by score, each with company, one-line summary,
sector/geo/function, score and source link. If nothing qualifies, it offers to widen the window —
**it never invents a signal**.

### Output (per signal)

```json
{
  "company": "…", "summary": "…", "type": "new_appointment",
  "sector": "food", "geography": "france", "contact_function": "supply_chain",
  "salience": "high", "date": "2026-06-27", "source_url": "https://…",
  "score": 1.0, "reason": "sector=food(1.0) geo=france(1.0) func=supply_chain(1.0)"
}
```

`score`: 1.0 = P1, 0.6 = P2, 0.3 = P3.

---

## Contents

```
emerton-signal-watch/
├── SKILL.md                       # what Claude reads first (when-to-use + workflow)
├── README.md                      # this file
├── build.sh                       # refresh bundled engine from src/ + rezip the .skill
├── targeting_matrix.json          # 3D targeting matrix (P1/P2/P3 — edit to retune)
├── triggers_module/
│   └── targeting_config.yaml      # RSS queries, keywords, sector/geo maps
└── scripts/
    ├── run_signals.py             # entrypoint: watch + qualify -> JSON/text
    └── bd_watch/                  # minimal scraping+scoring package (steps 01-02)
        ├── config.py  schemas.py
        ├── steps/     step01_watch.py  step02_qualify.py
        └── scrapers/  rss.py  press.py
```

> The config files sit at the **skill root** (not under `scripts/`) on purpose: the `bd_watch`
> modules resolve them relative to their own location (`parents[3]`), which is the skill root once
> the package lives under `scripts/`.

---

## Tuning the targeting

Editing `targeting_matrix.json` is the supported way to retune priorities (add a P1 sector, promote a
geography, …) — no code change needed. `triggers_module/targeting_config.yaml` controls *what* gets
scraped (RSS queries, role→function mapping, company→sector hints).

---

## Where this fits in the pipeline

`bd-watch` is **watch → qualify → contact → draft → review**. This skill is the **watch + qualify**
front end: it produces the *why* and the *who-shaped target* (company + function + reason). Feed its
output to the contact-discovery step, then to **`emerton-message-drafter`** for the message. Keep this
skill focused on detection + scoring; do not fold contact lookup or drafting into it.
