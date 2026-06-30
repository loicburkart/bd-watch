# bd-watch

**Business Development Watch + Outreach Drafter.**

Monitors our CRM, client news and the sector press to spot reasons to reach out — a
press article, a new appointment, a dormant relationship — then identifies the right
contact and drafts a personalised outreach message in the right tone.

---

## 📨 The deliverable: `emerton-message-drafter` (Claude Skill)

The **drafting step (04)** of this pipeline ships as a standalone, installable **Claude Skill** — the
primary deliverable. It runs **inside Claude** (desktop / Cowork): no API key, no server, no code to
run. Give it an Excel of contacts and it writes, per contact, one **email** + one **LinkedIn message**,
in the right language, in Emerton's formal register, grounded **strictly** in each row's facts and
laid out **email-ready** (subject / greeting / paragraphs / CTA / signature on their own lines). Output
is a **review document for a human — it never sends.**

**→ All hackathon skills index: [`skills/README.md`](skills/README.md)** — every skill the team built
(Watch · Qualify · Contact · Draft · Review), with owners, locations and status.
**→ Message-drafter docs: [`skills/emerton-message-drafter/README.md`](skills/emerton-message-drafter/README.md)**
(install steps, usage, output format, the binding `drafting_rules.md`, and per-shape input schemas.)

### Three input shapes (auto-detected by columns)

| Shape | What it is | Reference |
|-------|-----------|-----------|
| **Known clients** | CRM deal export — re-engage/activate (`Interaction History`, `Days Since`). | [`input_known_clients.md`](skills/emerton-message-drafter/references/input_known_clients.md) |
| **New prospects** | Cold leads tied to an external trigger. | [`input_new_prospects.md`](skills/emerton-message-drafter/references/input_new_prospects.md) |
| **Lost deals** | Lost-deal post-mortem — re-engage after a loss (`Deal Info`, `Post-Mortem Context`, `Suggested Next Step`). | [`input_lost_deals.md`](skills/emerton-message-drafter/references/input_lost_deals.md) |

### Install & use

1. Install the packaged skill: in Claude desktop / Cowork → **Customize → Skills → "+"**, upload
   [`skills/emerton-message-drafter.skill`](skills/emerton-message-drafter.skill). (Rebuild after edits:
   `cd skills && zip -r emerton-message-drafter.skill emerton-message-drafter -x '*/__pycache__/*'`.)
2. In a chat, attach a contacts Excel and say *"Draft outreach from this file."*
3. The skill asks **once** for: the **sender** (name + title — always required at launch, no default),
   the **default language** (FR/EN), and the **output location**, then produces the review document.

### ⚠️ Non-negotiable warnings (full version in the skill's `drafting_rules.md`)

- **Never auto-send.** Every draft is for human review.
- **No fabrication.** Use only facts in the row — never invent a figure, percentage, result, client
  name, or meeting. A number may appear only if it is verbatim in the input.
- **Perspective discipline.** Interaction history is *Emerton's internal record*; never attribute our
  meetings/colleagues/internal steps to the recipient. A proposal "sent internally" was not sent to them.
- **Lost deals — never mention the loss.** No rejection, lost date, deal amount, competitor guesses,
  internal colleague names or phone numbers. `Post-Mortem Context` / `Suggested Next Step` set the angle
  only — never quoted. Don't draft `archive_candidate` / `no_contact` rows; honour `hold_until` timing.
- **Sender is supplied each run** — never hardcoded, carried over, or invented; placeholder until given.
- **One shared email per row; one distinct 1-to-1 LinkedIn per recipient.** Formal register, vouvoiement
  in French, no exclamation marks. Language-aware length: EN email 90–130 / LinkedIn 45–75; FR 80–120 / 40–70.

> The skill is self-contained and usable on its own, but is designed as the final **draft** stage after
> the upstream steps (watch → qualify → contact). See the pipeline below.

---

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

### Multiple contacts on one deal

A deal cell may name several people (e.g. `Eric GRESSIER / Caroline SIZARET`). They
share one deal, so the feeder keeps a **single request** carrying every name in
`DraftRequest.recipients`. Step 04 then produces **one shared email** that greets all of
them together, and **one 1-to-1 LinkedIn message per recipient** (LinkedIn is not a
group channel). `OutreachDraft.linkedin` is therefore a list, validated per recipient.

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

This project uses [uv](https://docs.astral.sh/uv/) for environment and dependency
management. Install it once: `curl -LsSf https://astral.sh/uv/install.sh | sh`.

```bash
uv sync                                # create .venv, install deps + dev tools
cp .env.example .env                   # then fill in your keys

uv run python -m bd_watch.pipeline --qualify-only 2>/dev/null  # signaux qualifiés (steps 01+02)
uv run python -m bd_watch.pipeline                             # pipeline complet (steps 01→05)
uv run pytest                                                  # tests
```

### Nominations scraper (Step 01 — RSS)

```bash
cd triggers_module
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