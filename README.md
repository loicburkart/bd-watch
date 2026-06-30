# bd-watch

**Business Development Watch + Outreach Drafter.**

Monitors our CRM, client news and the sector press to spot reasons to reach out — a
press article, a new appointment, a dormant relationship — then identifies the right
contact and drafts a personalised outreach message in the right tone.

## Pipeline

The system runs as a sequence of steps, each owned by a teammate. Data flows step to
step through the shared schemas in `src/bd_watch/schemas.py`.

| Step | Module | Role |
|------|--------|------|
| 01 — Watch | `steps/step01_watch.py` | Scan CRM, client news and sector press; emit raw `Trigger`s. |
| 02 — Qualify | `steps/step02_qualify.py` | Score and filter triggers; keep the ones worth acting on. |
| 03 — Contact | `steps/step03_contact.py` | Identify the right contact and build their `ContactProfile`. |
| 04 — Draft | `steps/step04_draft.py` | Draft a personalised email + LinkedIn message. |
| 05 — Review | `steps/step05_review.py` | Apply guardrails; route to human review or send. |

`pipeline.py` wires the steps together end to end.

## Quickstart

This project uses [uv](https://docs.astral.sh/uv/) for environment and dependency
management. Install it once: `curl -LsSf https://astral.sh/uv/install.sh | sh`.

```bash
uv sync                                # create .venv, install deps + dev tools
cp .env.example .env                   # then fill in your keys

uv run python -m bd_watch.pipeline     # run the pipeline on sample data
uv run pytest                          # run the test suite
```

### Nominations scraper (Step 01 — RSS)

```bash
cd nominations_module
python nominations_scraper.py --dry-run   # fetch + display, no file written
python nominations_scraper.py             # writes output/nominations_today.json
```

### MergerMarket scraper (Step 01 — disabled by default)

Set `MERGERMARKET_ENABLED=true` in `.env` to activate, then:

```bash
uv run playwright install chromium
uv run python -m bd_watch.scrapers.mergermarket --setup   # log in once
uv run python -m bd_watch.scrapers.mergermarket --scrape
```

The Python version is pinned in `.python-version`; `uv` fetches it automatically.
Dependencies are locked in `uv.lock` — commit it, and run `uv lock` after changing
`pyproject.toml`.


## Layout

```
bd-watch/
├── src/bd_watch/
│   ├── config.py        # env + settings
│   ├── schemas.py       # shared data contracts between steps
│   ├── pipeline.py      # orchestrator + CLI entrypoint
│   └── steps/           # one module per pipeline step (stubs to fill in)
├── data/samples/        # sample inputs for local runs
└── tests/               # tests per step
```

## Working agreement

- Each step reads a typed input and returns a typed output from `schemas.py`. Keep the
  contracts stable so steps stay independent.
- Put sample/mock data in `data/samples/` so every step is runnable on its own.
- Secrets go in `.env` (git-ignored), never in code.