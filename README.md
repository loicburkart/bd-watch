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

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then fill in your keys

python -m bd_watch.pipeline   # runs the pipeline on sample data
```

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