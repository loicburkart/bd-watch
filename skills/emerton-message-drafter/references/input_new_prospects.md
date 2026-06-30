# Input: new prospects (cold leads)

Newly identified people to reach for the first time, each tied to an external reason to
reach out (a "trigger"). No prior relationship.

## Columns (a reasonable superset; map flexibly)

| Column | Meaning / use |
|--------|---------------|
| `Company` | Target company. |
| `First Name` + `Last Name` (or `Contact Name`) | The person to address. |
| `Contact Role` / `Title` | Drives register. |
| `Trigger Type` | e.g. new_appointment, funding_round, press_article, new_regulation, event. |
| `Trigger Summary` | 1–2 factual sentences on the event — the email opens on this. |
| `Source URL` | Where the trigger was found (for traceability; usually not pasted). |
| `Date` | When the event happened. |
| `Language` | fr / en (if absent, infer from the contact; flag `language_assumed`). |
| `Known Priorities` / `Notes` | Optional personalisation hooks. |

## How to interpret

- **Relationship:** `cold` (occasionally `warm` if there's a light prior touch).
- **Open on the trigger**, not on Emerton. Show why *now* and why *them*.
- One contact per row → one email + one LinkedIn message (1-to-1).
- Same hard rules apply: no invented figures, no fabricated history, formal register.

## Skip / triage

- Skip rows without a contact name or without any trigger (nothing to open on).
- Thin trigger (vague summary) → draft cautiously, `confidence: medium/low`.
