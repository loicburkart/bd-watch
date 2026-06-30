# emerton-message-drafter — Claude Skill

The **message-drafting** step of the `bd-watch` BD pipeline, packaged as a standalone Claude
Skill. Given an Excel of contacts, it writes — per contact — one **email** and one **LinkedIn
message**, in the right language, in Emerton's formal register, grounded **strictly** in each
row's facts. It runs **inside Claude** (desktop / Cowork): no API key, no server, no code to run.

The output is always a **review document for a human** — the skill drafts, it never sends.

---

## What it does

1. Reads the first sheet of a contacts Excel.
2. Detects the input shape (known clients vs. new prospects — see below).
3. Cleans the rows (skips junk/legend rows, drops duplicates, splits multi-person cells,
   infers relationship + seniority) via `scripts/parse_deals.py`.
4. Drafts one email + one LinkedIn message per valid contact, following the binding spec in
   `references/drafting_rules.md`.
5. Writes a single Markdown review document, grouped by contact, with a `confidence` level and
   `flags` on every entry.

### Three input shapes (auto-detected by columns)

| Shape | What it is | Relationship | Schema |
|-------|-----------|--------------|--------|
| **Known clients** | A CRM deal export (re-engagement / "activation"). Has `Interaction History` / `Days Since`. | `existing_client` (<14 days) / `dormant` | `references/input_known_clients.md` |
| **New prospects** | Newly identified leads, each tied to an external trigger (cold outreach). | `cold` | `references/input_new_prospects.md` |
| **Lost deals** | A lost-deal post-mortem — re-engage after a loss. Has `Deal Info`, `Post-Mortem Context`, `Suggested Next Step`. | `dormant` + `deal_status: lost` | `references/input_lost_deals.md` |

> **Lost deals are the delicate one.** `Post-Mortem Context` and `Suggested Next Step` are **internal
> strategy notes** (loss date, amount, competitor guesses, internal colleague names, phone numbers,
> targeting-matrix scores). They set the *angle* but must **never** appear in a message — and the loss
> itself is never mentioned. The message opens forward (a development in the field, an adjacent active
> programme, a neutral check-in).

---

## Installation

The skill ships as a single `.skill` file (a zip with the folder as its root).

**Install (per person):**
1. In Claude desktop / Cowork: **Customize → Skills → "+"** and upload `emerton-message-drafter.skill`. Uploaded skills are private to your account.

**Rebuild the `.skill` after editing the source:**
```bash
cd bd-watch/skills
zip -r emerton-message-drafter.skill emerton-message-drafter -x '*/__pycache__/*'
```

(Docs: https://support.claude.com/en/articles/12512198-how-to-create-custom-skills)

---

## Usage

In a Claude / Cowork chat, attach a contacts Excel (a `Deal_Reminders`-style CRM export, or a
new-prospects list) and say something like *"Draft outreach from this file."*

Claude will, **once**, ask you for:
1. **Sender** — name + title to sign as (format: "<First Last>, <Title>, Emerton Data"). **Always required at launch — no default, never carried over or invented.** The signature uses exactly the sender you give; until then it stays the literal placeholder `[Sender Name] — [Sender Title]`.
2. **Default language** — FR or EN, used when a row doesn't specify.
3. **Output location** — where to save the review document.

It then produces the review doc. **Always review before sending.**

### Output format (per contact) — email-ready

Every message is rendered in its own fenced code block, laid out like a real email so it can be
**copy-pasted straight into an email/LinkedIn** — subject, greeting, short paragraphs, CTA and
signature on their own lines, never collapsed into one block.

````
### <Company> — <Contact name(s)>
**Relationship:** <…> · **Language:** <fr|en> · **Context:** <one safe line>

**Email** — _subject: <≤60 chars>_

```text
Bonjour <Prénom>,

<paragraph 1>

<paragraph 2>

<CTA — single ask, own line>

Bien à vous,
<Sender> — <Title>
```

**LinkedIn — <name>**

```text
<EN 45–75 / FR 40–70 words, distinct from the email>
```

**Review:** confidence: <high|medium|low> · flags: <very_stale, thin_data, language_assumed, hold_until:<date>, addressee_review, none>
````

---

## ⚠️ Important warnings

These are the rules that make the output safe to put in front of a client. They are enforced in
`references/drafting_rules.md`; treat them as non-negotiable.

- **Never auto-send.** Every draft is for human review. Low-confidence / flagged items especially.
- **No fabrication.** Use only facts present in the row. Never invent a figure, percentage, result,
  client name, or meeting. A number may appear in a message **only** if it is verbatim in the input
  (e.g. the prospect trigger's "$2bn"). With no grounded figure, make the point qualitatively or omit it.
- **Perspective discipline (the subtle one).** For known clients, the interaction history is
  **Emerton's internal CRM record**. Our meetings, our colleagues, our deck sends, our internal
  proposal drafts are *our* actions — never attribute them to the recipient. Reference only what the
  row explicitly says the contact did ("your message of 12 June", "the presentation you attended").
  A proposal "sent internally" has **not** been sent to the client.
- **Channels.** One **shared** email greeting all named recipients on a row; one **separate, distinct**
  1-to-1 LinkedIn message per recipient. LinkedIn is never a group note and never a copy of the email.
- **Register.** Formal, corporate, vouvoiement in French. No effusive openers ("ravi"), no exclamation
  marks, no sales clichés ("aucune pression", "quick win"). Open on the contact/trigger, never on Emerton.
- **Length is language-aware.** French prose is denser, so the bands differ: EN email 90–130 /
  LinkedIn 45–75; **FR email 80–120 / LinkedIn 40–70**. The band is a check, not a target — never pad
  to reach a minimum.
- **Triage honestly.** Very stale (> 180 days) or thin-data rows are still drafted, but kept generic,
  marked `confidence: low`, and flagged — never given an invented reason to reconnect.
- **Lost deals — never mention the loss.** No rejection, no lost date, no deal amount, no competitor
  guesses, no internal colleague names or phone numbers from the post-mortem. Use `Suggested Next Step`
  as the angle only, never as text. Don't draft `archive_candidate` (P4) or `no_contact` rows — triage
  them. Honour timing holds (`hold_until`).

### Data-quality gotchas seen in real inputs
- Rows where a single text field is **copy-pasted across several contacts** (e.g. a `rationale` that
  only describes one person). Draft from the structured fields (name/title/company/trigger), not the
  duplicated blob, and flag it.
- Cold-emailing a **global CEO** found in a prospect list is usually the wrong channel — flag
  `seniority_mismatch` and suggest routing via local leadership.
- Multiple contacts at the **same company on the same trigger** are drafted individually but should be
  **coordinated before sending**.

---

## Contents

```
emerton-message-drafter/
├── SKILL.md                      # what Claude reads first (when-to-use + workflow)
├── README.md                     # this file
├── references/
│   ├── drafting_rules.md         # the binding spec (tone, perspective, no-fabrication, lengths, format)
│   ├── input_known_clients.md    # CRM deal export schema
│   ├── input_new_prospects.md    # cold-leads schema
│   └── input_lost_deals.md       # lost-deal post-mortem schema (+ internal-fields rules)
└── scripts/
    └── parse_deals.py            # Excel -> clean JSON (detects type, skips junk, dedups). Needs openpyxl.
```

---

## Where this fits in the pipeline

`bd-watch` is **watch → qualify → contact → draft → review**. This skill is the **draft** step. It is
self-contained and usable on its own (attach an Excel, get drafts), but it is designed to be the final
writing stage after the upstream skills identify *why* to reach out (watch/qualify) and *who* to address
(contact).

**When merging with the other pipeline skills:** keep this one focused on drafting only — it should
receive a contact + a grounded reason-to-reach-out and produce the messages. Don't fold
signal-detection or contact-discovery into it; those belong to the upstream skills. The shared contract
is simple: a contact (name, title, company, language, relationship) plus the row/trigger facts in,
review-ready email + LinkedIn out. The hard rules above (no fabrication, perspective, never auto-send)
stay owned here regardless of how the upstream skills evolve.
