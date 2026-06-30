# Input: lost deals (post-mortem re-engagement)

A list of **lost** deals to consider re-approaching. Example file:
`Lost_Deals_PostMortem_*.xlsx`. Each row is one lost deal (a contact may appear on several
distinct deals — keep them separate). The point is to re-open a conversation **without ever
referring to the loss**.

## Columns (names may vary slightly)

| Column | Meaning / use |
|--------|---------------|
| `#` | Row id. |
| `Priority` | P1 (re-engage now) → P4 (archive). Drives whether to draft at all. |
| `Company` | Account. May be blank/unknown on junk rows. |
| `First Name` + `Last Name` (or `Contact Name`) | The person. A stray `None` token is cleaned out. |
| `Contact Role` | Title → register. |
| `Contact Email` | If present. |
| `Deal Info (scope | amount | lost)` | One cell holding the **scope** (first line), the **amount**, and the **lost date**. The parser splits these into `scope`, `deal_amount_internal`, `lost_date`. |
| `Proj Type`, `Re-engagement Window`, `Timing` | When to act. |
| `Collab Potential` | Internal assessment of the opportunity. |
| `Post-Mortem Context` | **INTERNAL.** Why it was lost, competitor guesses, internal contact lists, phone numbers, role gossip, targeting-matrix scores. |
| `Suggested Next Step` | **INTERNAL.** The recommended angle / who to approach / what NOT to do. |

## How to interpret

- **Relationship:** `dormant` with `deal_status: lost`. There was a prior relationship; treat the
  contact as someone we've engaged before, not a cold lead.
- **The scope is a safe, factual hook** ("Revenue Growth Management", "MMM refresh", "GenAI for
  creative production"). The lost date, amount, competitor and loss reason are **not**.
- **Use `Suggested Next Step` as the angle, never as text.** It often says things like "don't
  re-pitch the original — propose a next phase", "approach X, not the original sponsor", "lead with
  curiosity", "frame as continuity", "bundle with the active programme". Follow that intent; never
  quote it, and never reveal the strategy ("we think you rejected us on price", "you're a role
  transition", etc.).

## Hard rules specific to lost deals

- **Never mention the loss, the rejection, the lost date, or that a deal "didn't go ahead."** Open
  forward: a relevant development, the evolution of the field, the progress of an adjacent active
  programme, or a neutral check-in.
- **Never cite the deal amount** (`€20k`, `€510k`, …). It is an internal commercial figure.
- **Never expose internal context**: competitor names/guesses, internal colleague names, phone
  numbers, "Gilles told us", targeting-matrix priorities, budget-cycle reasoning.
- **Respect the addressee guidance.** If `Suggested Next Step` says to approach a *different* person
  than the row's contact, draft to the row's contact but flag `addressee_review` with the suggested
  name — don't silently invent details for someone not in the row.

## Skip / triage (do not force a draft)

- `no_contact` (no name / unknown company) → **don't draft**; list under triage with the internal
  next step (usually "find the originating Emerton owner").
- `archive_candidate` (P4, or next step = "Archive") → **don't draft**; list under triage. Drafting
  outreach for an explicit archive is counter-productive.
- `hold_until_window` / `Timing` = "too early" → you may draft, but flag `hold_until` with the date
  from the window; the message is prepared, not for sending yet.
- Old losses (> 12 months) with a thin hook → draft cautiously, `confidence: low`, kept generic.
