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

## Feeders — two front doors, one drafter

There are two ways a reason-to-reach-out enters the system. Both converge on the same
`DraftRequest`, so the single drafter (step 04) handles them with no special-casing —
it adapts purely through the `relationship` field on the contact. See
`src/bd_watch/feeders.py`.

| Feeder | Source | Use case | Relationship |
|--------|--------|----------|--------------|
| `cold_feeder` | External triggers (news, press, appointments) via steps 01→03 | **Cold contact** — no prior relationship | `cold` |
| `activation_feeder` | The CRM deal export (`.csv` / `.xlsx`) | **Database activation** — re-engage known contacts on quiet deals | `dormant` / `existing_client` |

`activation_feeder` reads each deal row and grounds the trigger in the *real*
interaction history and recent-discussion summary, so the draft references the actual
last exchange rather than a generic proof point. A deal quiet for ≥ 14 days is treated
as `dormant`, otherwise `existing_client`. Point it at your export with
`CRM_EXPORT_PATH` (defaults to the anonymized `data/samples/crm_deals_sample.csv`).

> The real CRM export contains client data and is **not** committed. Keep it local and
> set `CRM_EXPORT_PATH`, or use the anonymized sample.

## 04 — Drafting Pipeline (LLM Core)

Step 04 (`src/bd_watch/steps/step04_draft.py`) is the core LLM engine of the platform. It takes the output from previous stages (the `DraftRequest`) and generates the final Email and LinkedIn messages. The logic functions as follows:

1. **Context-Aware Decision Tree**:
   Before querying the LLM, the python pipeline evaluates the context of the contact using a helper decision-tree function. It checks the contact's `seniority` (e.g., C-Level vs VP), the `relationship` (e.g., Cold vs Warm vs Dormant), and the target `language`.
2. **Dynamic Prompt Assembly**:
   Based on the decision tree, exact adaptation rules are injected into the overarching `SYSTEM_PROMPT`. For instance, if the contact is C-Level, the prompt is instructed to be highly concise and strategic. If the relationship is Cold, the model is told to build quick legitimacy and provide immediate value based on the trigger.
3. **Execution**:
   Using the `anthropic` client (and the `ANTHROPIC_API_KEY` from your environment), it constructs the final instruction containing the trigger details, Emerton assets, style reference, and the modified rules. It then expects a strictly structured JSON response containing the message bodies and subject lines.
4. **Mock Fallback**:
   If the `ANTHROPIC_API_KEY` is not present, Step 04 gracefully degrades into a mocked draft mode, returning a hardcoded output. This guarantees that local developers missing an API key can still successfully run the pipeline demo end-to-end.

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
│   ├── feeders.py       # two feeders (cold + activation) -> DraftRequest
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