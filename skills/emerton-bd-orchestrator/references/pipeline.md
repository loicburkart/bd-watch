# Pipeline contracts & stage availability

The orchestrator chains five stages. Data flows through the typed dataclasses in
`src/bd_watch/schemas.py` — keep those contracts stable so stages stay independent.

## Stage contracts

| Stage | Consumes | Produces | Where it lives (on `main`) | Status |
|-------|----------|----------|----------------------------|--------|
| **01 Watch** | configured sources | `Trigger[]` (raw reasons-to-reach-out) | `triggers_module/`, `src/bd_watch/scrapers/`, `steps/step01_watch.py` | Merged & implemented (Google News RSS + Actu News API + press/MergerMarket → News Aggregator). |
| **02 Qualify** | `Trigger[]` | `QualifiedTrigger[]` (P1–P4) | `steps/step02_qualify.py` + `targeting_matrix.json` | Merged. Matrix present; `step02_qualify` scoring is still **heuristic/naive** (salience-based). |
| **03 Contact ID** | `QualifiedTrigger` | `ContactProfile` | `src/bd_watch/identify_contact/` (module) + `steps/step03_contact.py` (hook) | Module merged (Lusha + web + LLM ranking), **but the pipeline hook `step03_contact.identify_contact()` still returns a mock profile** — wiring pending. |
| **CRM ingestion** | HubSpot export (`.xlsx`) | `DraftRequest[]` (reminders + post-mortems) | `src/bd_watch/feeders.py` (activation feeder) + the drafter's `parse_deals.py` | Working. |
| **04 Draft** | `ContactProfile` / `DraftRequest` | `OutreachDraft` (email + LinkedIn) | **`skills/emerton-message-drafter/`** (packaged skill) | ✅ Packaged & on `main`. |
| **05 Review** | `OutreachDraft` | `ReviewedOutreach` (send / human_review / discard) | `steps/step05_review.py` | Minimal rule: ready only if confidence `high` & no flags. |

## How to run each stage (repo context)

- **Whole code pipeline (where modules are present):** `python -m bd_watch.pipeline`
- **CRM Excel → normalised rows (drafter parser):**
  `python ../emerton-message-drafter/scripts/parse_deals.py <file.xlsx>`
- **Watch CLI (only on `feat/nominations-module`):** `python triggers_module/nominations_scraper.py`
- **Draft:** use the `emerton-message-drafter` skill (don't re-implement its rules).

## Availability summary

- **CRM path** (Excel → Draft → Review): **fully available now.**
- **Discovery path** (Watch → Qualify → Contact → Draft → Review): **runs end-to-end on `main`** via
  `python -m bd_watch.pipeline`, but with two known gaps to flag in the run report:
  1. **Contact resolution is mocked** — `step03_contact.identify_contact()` returns a placeholder profile;
     the real `src/bd_watch/identify_contact/` module (Lusha + web + LLM) is **not yet wired into the hook**.
     Treat identified people as `contact_unverified` until that wiring lands.
  2. **Qualify scoring is heuristic** — `step02_qualify` uses salience, not the full targeting matrix yet.
- The orchestrator never fabricates a trigger, contact, or fact to fill a gap — it marks them
  `pending`/`unverified` and proceeds.

When step03 is wired to `identify_contact` and matrix scoring is finished, **no orchestrator change is
needed**: it already calls each stage in order through the shared schemas.
