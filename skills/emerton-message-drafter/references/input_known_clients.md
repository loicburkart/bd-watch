# Input: known clients (CRM deal export)

A re-engagement / "activation" list of contacts we already know. Example file:
`Deal_Reminders_*NoEmail*.xlsx`. First sheet holds the deals; a second sheet may hold a
priority legend (ignore it).

## Columns (names may vary slightly)

| Column | Meaning / use |
|--------|---------------|
| `#` | Row number. Non-numeric rows (e.g. "Legend:") are footers — skip. |
| `Priority` | P1–P4. Higher = more urgent; can inform salience and ordering. |
| `Company` | Account. May be blank on junk rows. |
| `Contact Name` *or* `First Name` + `Last Name` | The person. Build the full name from First+Last if there's no single column. A cell may name several people ("Eric GRESSIER / Caroline SIZARET") — keep them as recipients of ONE shared email + one LinkedIn each. |
| `Contact Role` | Title → drives register (C-level/VP/Director/Manager). |
| `Scope of Discussion` | The open topic — a key personalisation hook. |
| `Next Step` | Our intended next action (internal). |
| `Last Action`, `Last Action Date`, `Days Since` | Recency. |
| `Interaction History` | Our internal log — **Emerton's perspective** (see rule 7). |
| `Summary of Recent Discussions` | Our internal summary. |
| `Additional Info` | Our internal notes. |

## How to interpret

- **Relationship:** `existing_client` if recently active (≈ < 14 days since contact),
  otherwise `dormant`. Very stale (> 180 days) → still dormant, but `confidence: low`.
- **Perspective:** everything in History / Summary / Notes is *our* record. Attribute
  internal steps to Emerton, never to the contact (rule 7 in drafting_rules.md).
- **Language:** the file usually has no language column. French accounts → FR.
  Contacts clearly outside France (e.g. Hong Kong, APAC, UK names/roles) → EN. If unsure,
  ask the user or flag `language_assumed`.

## Skip / triage

- Skip rows with no real contact name (placeholder "—", blank, or legend/footer).
- Collapse duplicate `(Company, Contact)` rows to one (flag `duplicate_collapsed`).
- Rows with a name but no company → draft but flag `missing_company`.
