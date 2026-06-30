---
name: emerton-bd-orchestrator
description: Orchestrate the full Emerton BD Watch pipeline end to end and produce one consolidated, review-ready outreach document. Runs the whole chain — Watch (news/triggers) → Qualify (priority matrix) → Contact identification (Lusha/web) → Draft (email + LinkedIn) → Review (send-gate) — and also handles the CRM path (HubSpot reminders & lost-deal post-mortems straight to drafting). Use when someone wants to "run the pipeline", "run BD watch", "generate this week's outreach", "process this CRM export end to end", or chain the sub-skills rather than run a single stage. Composes the other skills; never re-implements them. Output is for human review — nothing is sent.
---

# Emerton BD Watch — Orchestrator

This skill is the **single entry point** that runs the whole BD outreach pipeline and returns one
consolidated, review-ready document plus a run report. It **coordinates** the sub-skills/modules — it
does not re-implement them. Like every skill in this suite, it **never sends**; output is for human review.

Pipeline (see `references/pipeline.md` for the stage contracts and current availability):

```
            ┌──────────── discovery path ────────────┐
Watch (01) → Qualify (02) → Contact ID (03) ───────────┐
                                                        ├─→ Draft (04) → Review (05) → consolidated review doc
CRM (HubSpot) → CRM Processor ──(reminders, post-mortems)┘
            └──────────────── CRM path ───────────────┘
```

## When to use

Use this skill when the request is **end-to-end** ("run the pipeline / BD watch", "generate this week's
outreach", "process this export and draft everything"). For a single stage (just draft an Excel, just
score triggers), call that stage's skill directly — e.g. `emerton-message-drafter` for a one-off Excel.

## Two entry paths (pick based on the request/input)

1. **CRM path** — the user supplies an Excel (CRM deal export / lost-deal post-mortem / prospect list),
   or asks to "re-engage known clients / lost deals". This path is **fully working today**: it goes
   straight to **Draft (04)** → **Review (05)**. No watch/contact needed (the contacts are in the file).
2. **Discovery path** — the user asks to find *new* reasons to reach out ("scan the news", "who got
   appointed / raised funding this week"). This runs **Watch (01) → Qualify (02) → Contact ID (03) →
   Draft (04) → Review (05)**. Some upstream stages are not yet merged to `main` (see availability) —
   degrade gracefully (below).

## Orchestration procedure

1. **Confirm scope once** (use the orchestrator's judgment; ask only if ambiguous):
   - Which path (CRM export vs. news discovery)? What region/sector/timeframe? And the **sender**
     (name + title — always required for drafting, no default).
2. **Run the helper to plan the run:** `python scripts/run_pipeline.py --input <file.xlsx>` (CRM path) or
   `python scripts/run_pipeline.py --discovery` (discovery path). It detects which stages are available,
   parses any Excel via the drafter's parser, and writes a **run manifest** (JSON) + prints a plan.
3. **Execute each available stage in order**, passing typed output to the next (contracts in
   `references/pipeline.md`). For a missing stage, follow *Graceful degradation*.
4. **Draft** — hand each resolved contact + its grounded context to the **`emerton-message-drafter`**
   skill. Do **not** re-implement its rules (formatting, no-fabrication, perspective, lost-deal handling,
   language-aware lengths). Let it produce the email + LinkedIn per contact.
5. **Review (05)** — apply the send-gate: a draft is "ready" only if confidence is `high` and flags are
   empty; otherwise mark `human_review` (or `hold`/`discard`). Nothing is auto-sent regardless.
6. **Consolidate & report** — write ONE review document grouped by contact (using the drafter's
   email-ready output format), preceded by a **run report**: path taken, stages run vs. skipped, counts
   (contacts in / drafted / triaged), confidence distribution, and anything `pending` because a stage
   isn't merged yet. Save to the agreed location.

## Graceful degradation (known gaps)

All five stages now exist as **code on `main`**; only **Draft (04)** is packaged as a Claude Skill. The
real gaps are *wiring/maturity*, not missing stages. Do the best honest thing and report it:

- **CRM path:** fully supported now — skip Watch/Qualify/Contact and go straight to Draft → Review.
- **Discovery path:** runs end-to-end (`python -m bd_watch.pipeline`), but:
  - **Contact ID (03) hook is mocked.** `step03_contact.identify_contact()` returns a placeholder; the real
    `src/bd_watch/identify_contact/` module (Lusha + web + LLM) isn't wired in yet. Flag every such contact
    `contact_unverified` and ask the user to confirm the person before anything is sent.
  - **Qualify (02) is heuristic** (salience, not the full targeting matrix). Label scoring `heuristic`.
- **If a stage genuinely returns nothing** (e.g. no triggers found), say so; ask the user to provide
  triggers/contacts rather than inventing them.
- **Never invent** a trigger, a contact, or a fact to fill a gap. Mark it `pending`/`unverified` and move on.

Always state in the run report which stages actually ran, which were heuristic/mocked, and what is unverified.

## Output

- **`outreach_run_review.md`** — run report header + per-contact drafts (delegated to `emerton-message-drafter`,
  email-ready), each with confidence/flags and the Review verdict.
- **`run_manifest.json`** (from the helper) — machine-readable record of the run: path, stage availability,
  parsed inputs, and counts.

## Non-negotiables (inherited from the sub-skills)

Never auto-send. No fabrication (use only grounded facts). Perspective discipline (internal CRM steps are
ours, never the recipient's). For lost deals, never mention the loss and never leak internal post-mortem
notes. Sender is supplied each run. These are enforced by `emerton-message-drafter` — do not override them.
