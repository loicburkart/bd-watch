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

1. **CRM path** — re-engage known clients / lost deals. The source spreadsheet is either supplied by the
   user or **generated on demand from HubSpot** by a CRM routine:
   - `crm-reminders-routine` → prioritised stale-deal `.xlsx` (drafter's **known-clients** input).
   - `crm-post-mortem-routine` → `Lost_Deals_PostMortem_[date].xlsx` (drafter's **lost-deals** input).
   Then go straight to **Draft (04)** → **Review (05)** (the contacts are in the file; no watch/contact needed).
   **Fully working today.**
2. **Discovery path** — find *new* reasons to reach out ("scan the news", "who got appointed / raised
   funding"). Runs **Watch (01) → Qualify (02) → Contact ID (03) → Draft (04) → Review (05)** via
   `emerton-signal-watch` (Watch + Qualify). `crm-prospects-for-news-screening` can supply a never-won
   prospect list to cross-reference against the news. The one gap: **Contact ID's pipeline hook is mocked**
   (see *Graceful degradation*).

## Orchestration procedure

1. **Confirm scope once** (use the orchestrator's judgment; ask only if ambiguous):
   - Which path (CRM export vs. news discovery)? What region/sector/timeframe? And the **sender**
     (name + title — always required for drafting, no default).
2. **Get the source data, then plan the run.**
   - *CRM path:* if the user didn't attach a spreadsheet, run the matching CRM routine first to generate it
     from HubSpot — `crm-reminders-routine` (known clients) or `crm-post-mortem-routine` (lost deals).
   - *Discovery path:* run `emerton-signal-watch` to get the qualified watchlist; optionally seed it from
     `crm-prospects-for-news-screening`.
   Then plan with `python scripts/run_pipeline.py --input <file.xlsx>` (CRM) or `--discovery`. The helper
   detects available stages, parses any Excel via the drafter's parser, and writes a **run manifest** (JSON).
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
- **Discovery path:** Watch + Qualify run via `emerton-signal-watch` (matrix scoring live). One gap:
  - **Contact ID (03) hook is mocked.** `step03_contact.identify_contact()` returns a placeholder; the real
    `src/bd_watch/identify_contact/` module (Lusha + web + LLM) isn't wired in yet. Flag every such contact
    `contact_unverified` and ask the user to confirm the person before anything is sent.
- **If a stage genuinely returns nothing** (e.g. no triggers found), say so; ask the user to provide
  triggers/contacts rather than inventing them.
- **Never invent** a trigger, a contact, or a fact to fill a gap. Mark it `pending`/`unverified` and move on.

Always state in the run report which stages actually ran, which were mocked, and what is unverified.

## Output

- **`outreach_run_review.md`** — run report header + per-contact drafts (delegated to `emerton-message-drafter`,
  email-ready), each with confidence/flags and the Review verdict.
- **`run_manifest.json`** (from the helper) — machine-readable record of the run: path, stage availability,
  parsed inputs, and counts.

## Non-negotiables (inherited from the sub-skills)

Never auto-send. No fabrication (use only grounded facts). Perspective discipline (internal CRM steps are
ours, never the recipient's). For lost deals, never mention the loss and never leak internal post-mortem
notes. Sender is supplied each run. These are enforced by `emerton-message-drafter` — do not override them.
