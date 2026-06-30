# emerton-bd-orchestrator (Claude Skill)

The **orchestrator** for the Emerton BD Watch suite. It runs the whole pipeline end to end and returns
**one consolidated, review-ready outreach document** plus a run report. It **composes** the other skills
— it never re-implements them — and, like the rest of the suite, **never sends**.

```
            ┌──────────── discovery path ────────────┐
Watch (01) → Qualify (02) → Contact ID (03) ───────────┐
                                                        ├─→ Draft (04) → Review (05) → consolidated review
CRM (HubSpot) → CRM Processor ──(reminders, post-mortems)┘
            └──────────────── CRM path ───────────────┘
```

## What it does

- Picks the **entry path**: the **CRM path** (an Excel export → straight to drafting; works today) or the
  **discovery path** (news watch → qualify → contact ID → draft).
- Runs each **available** stage in order through the shared `schemas.py` contracts, delegates **drafting**
  to `emerton-message-drafter`, applies the **Review** send-gate, and **consolidates** everything into one
  review document with a run report.
- **Composes the packaged skills**: `emerton-signal-watch` (Watch + Qualify, matrix scoring live), the
  `crm-*` routines (generate the HubSpot spreadsheets), and `emerton-message-drafter` (drafting).
- **Degrades gracefully**: the one real gap is the **mocked contact hook** (step03 not yet wired to the
  merged `identify_contact` module). The orchestrator flags it `contact_unverified`, accepts
  manually-provided triggers/contacts, and **never fabricates** to fill a gap.

## Install

In Claude desktop / Cowork → **Customize → Skills → "+"**, upload `emerton-bd-orchestrator.skill`.
For the full experience, also install **`emerton-message-drafter`** (the orchestrator delegates drafting
to it). Rebuild after edits:
`cd skills && zip -r emerton-bd-orchestrator.skill emerton-bd-orchestrator -x '*/__pycache__/*'`

## Use

Say *"run the BD pipeline on this export"* (attach an Excel) or *"run BD watch for new appointments in
France this week"*. The skill confirms scope + sender, plans the run, executes the available stages,
and saves `outreach_run_review.md` + `run_manifest.json`.

Helper (repo context):
```bash
python scripts/run_pipeline.py --input <file.xlsx>   # CRM path: parse + plan
python scripts/run_pipeline.py --discovery           # discovery path: availability + plan
```

## Contents

```
emerton-bd-orchestrator/
├── SKILL.md                 # when-to-use + the orchestration procedure + graceful degradation
├── README.md                # this file
├── references/
│   └── pipeline.md          # stage contracts, run commands, current availability
└── scripts/
    └── run_pipeline.py      # detects available stages, parses any Excel, writes a run manifest
```

## Status & dependencies

- **CRM path: fully working now** — the `crm-reminders-routine` / `crm-post-mortem-routine` skills
  generate the spreadsheet from HubSpot (or the user supplies it), then Draft → Review.
- **Discovery path: runs end-to-end on `main`** via `emerton-signal-watch` (Watch + Qualify, matrix scoring
  live). One gap the run report flags: **contact resolution is mocked** (step03's hook isn't wired to the
  merged `src/bd_watch/identify_contact/` module yet → `contact_unverified`). When step03 is wired, **no
  orchestrator change is needed** — it already calls each stage through the shared schemas.
- Delegates drafting to **`emerton-message-drafter`**; do not duplicate its rules here.

See the suite index — [`../README.md`](../README.md) — for all skills and the functional architecture.
