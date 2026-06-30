# Emerton BD Watch — Hackathon skills

This folder is the home for the **skills built during the Emerton hackathon**. The project,
`bd-watch`, is a Business Development watch-and-outreach assistant: it spots a reason to reach out,
finds the right person, drafts the message, and gates it for human review. Each stage was built by a
different teammate as its own skill/module; together they form one pipeline:

```
Watch → Qualify → Contact → Draft → Review
 (why now?)  (worth it?)  (who?)   (write)  (safe to send?)
```

> **Packaging status.** Only the **message drafter** is currently packaged as an installable Claude
> Skill (`emerton-message-drafter/` + `.skill`). The other stages live as Python modules / CLIs on
> their feature branches and are being consolidated onto `main`. This index documents all of them so
> the team has one place to see what exists, where it lives, and what state it's in.

## The skills at a glance

| # | Skill | What it does | Owner | Lives in | Status |
|---|-------|--------------|-------|----------|--------|
| 01 | **Watch / Triggers** | Scans Google News RSS (nominations, appointments, funding) and MergerMarket/press for reasons to reach out; emits raw signals/triggers. | Benjamin | branch `feat/nominations-module`: `triggers_module/`, `src/bd_watch/scrapers/`, `steps/step01_watch.py` | Implemented (RSS live; MergerMarket via Playwright) |
| 02 | **Qualify / Targeting matrix** | Scores & filters triggers on the 3-axis matrix (offer × sector × geography → P1–P4); keeps the ones worth acting on. | team | `steps/step02_qualify.py` + `targeting_matrix.json` / `targeting_config.yaml` | Matrix defined; scoring being wired (currently naive salience) |
| 03 | **Contact identification** | From a signal, deduces the target profile, finds candidates via **Lusha + web scraping**, ranks them with an LLM, enriches the top 3; checks CRM first for existing relationships. | team | branch `feature/search_contact`: `src/bd_watch/identify_contact/` | Module implemented (pipeline, reasoning, Lusha client, web fallback) |
| 04 | **Message drafter** ⭐ | Turns an Excel of contacts into review-ready outreach — one email + one 1-to-1 LinkedIn per contact, email-ready, grounded strictly in the row. | Loïc | **`emerton-message-drafter/`** (packaged `.skill`) | ✅ Packaged & merged to `main` |
| 05 | **Review** | Guardrail gate: auto-send only if confidence is high and no flags; otherwise route to human review or discard. | team | `steps/step05_review.py` | Minimal rule in place |

Data flows through the shared typed contracts in `src/bd_watch/schemas.py`, so each skill can be built
and run independently. `src/bd_watch/pipeline.py` wires them end to end.

---

## 01 — Watch / Triggers  ·  `feat/nominations-module`

Detects *why now*. A standalone CLI (`triggers_module/nominations_scraper.py`) fetches nomination and
appointment news from Google News RSS (broad French/English queries in `targeting_config.yaml`, filtered
post-fetch on target roles), with additional `scrapers/` for press and MergerMarket. Output is written
as `RawSignal`s for the next stage; scoring is intentionally **not** done here (that's Qualify).

## 02 — Qualify / Targeting matrix

Decides *is it worth it*. Scores each trigger on Emerton's three axes — functional/offer, sector, and
geography — to a P1–P4 priority, and filters out the noise. The matrix lives in `targeting_matrix.json`
(and `targeting_config.yaml`); `steps/step02_qualify.py` applies it. (Currently a naive salience mapping
is in place while the full matrix scoring is wired in.)

## 03 — Contact identification  ·  `feature/search_contact`

Decides *who to address*. `src/bd_watch/identify_contact/` is a full module:
`signal → deduce target profile → candidates (Lusha + web scraping) → LLM ranking → enrich top 3`, with a
CRM check first so an existing/dormant relationship is reactivated rather than treated as cold. Produces
a `ContactProfile` for the drafter.

## 04 — Message drafter ⭐  ·  packaged Claude Skill

Writes the message. This is the one packaged, installable Claude Skill. It takes a contact (plus the
trigger/row context) and produces a review-ready email + LinkedIn message in Emerton's formal register,
grounded strictly in the facts, and **never sends**.

**→ Full documentation: [`emerton-message-drafter/README.md`](emerton-message-drafter/README.md)**
— install steps, usage, the three input shapes (known clients / new prospects / lost-deal post-mortems),
the email-ready output format, the binding `drafting_rules.md`, and all the non-negotiable warnings
(no fabrication, perspective discipline, never mention a lost deal, sender supplied each run, etc.).

Install: in Claude desktop / Cowork → **Customize → Skills → "+"**, upload
[`emerton-message-drafter.skill`](emerton-message-drafter.skill).

## 05 — Review

The safety gate. `steps/step05_review.py` auto-sends only when the draft's confidence is `high` and there
are no flags; everything else is routed to human review (or discarded). In practice nothing auto-sends —
the drafter always returns a review document.

---

## For the team — consolidating onto `main`

- The drafter is on `main` and packaged. The Watch and Contact skills are on their branches
  (`feat/nominations-module`, `feature/search_contact`) and need merging in; Qualify/Review live on
  `main` as the base pipeline steps.
- Keep the **shared contracts** in `src/bd_watch/schemas.py` stable — they are what let these skills stay
  independent and plug together.
- As each stage matures, it can follow the drafter's pattern and be packaged as its own installable
  `.skill` (a folder with `SKILL.md` + `references/` + `scripts/`, zipped with a `.skill` extension).
