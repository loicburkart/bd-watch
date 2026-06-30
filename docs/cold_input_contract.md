# Cold-call input contract

What the **cold contact** use case needs from the rest of the project, before step 04
(drafting) can run. This is the hand-off between the upstream teams and the drafter.

A cold lead is one *(trigger, contact)* pair: an external reason to reach out plus the
right person to reach. The shared Emerton assets (offer, proof points, sender, style)
come once from the credentials base, not per lead.

```
Watch / detection (steps 01–02)  ─┐
                                  ├─►  cold lead = { trigger, contact }  ─►  cold_feeder  ─►  DraftRequest  ─►  step 04
Contact identification (step 03) ─┘
Credentials base (assets + style) ───────────────────────────────────────────────────────┘
```

The canonical example lives in [`data/samples/cold_leads_sample.json`](../data/samples/cold_leads_sample.json).
The file is `{ "schema_version": "1.0", "leads": [ <lead>, ... ] }`.

---

## Lead object

Each lead has a `trigger` and a `contact`, plus an id.

| Field | Type | Required | Provided by | Notes |
|-------|------|----------|-------------|-------|
| `lead_id` | string | yes | Watch | Stable unique id, used for dedup and tracing. |
| `trigger` | object | yes | Watch / detection | The reason to reach out. See below. |
| `contact` | object | yes | Contact identification | The person to reach. See below. |

### `trigger`

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `type` | enum | yes | One of: `press_article`, `new_appointment`, `funding_round`, `new_regulation`, `event`. (`dormant_relationship` is the activation use case, not cold.) |
| `summary` | string | yes | 1–2 factual sentences. This is what the email opens on — be specific, no spin. |
| `source_url` | string (URL) | yes | Link to the source. Used for traceability; the drafter does not paste it unless useful. |
| `date` | string (ISO `YYYY-MM-DD`) | yes | When the event happened. Drives recency/salience. |
| `company` | string | yes | The company the trigger concerns. |
| `salience` | enum | recommended | `high` / `medium` / `low`. Defaults to `medium` if omitted. |
| `evidence` | string | optional | Short note on why this is real/strong (reactions, who said it). For human review, not sent. |

### `contact`

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `full_name` | string | yes | The person to address. |
| `title` | string | yes | Their role; drives register together with seniority. |
| `company` | string | yes | Should match `trigger.company`. |
| `seniority` | enum | recommended | `C-level` / `VP` / `Director` / `Manager`. Defaults to `Manager` if omitted. |
| `language` | enum | recommended | `fr` / `en`. The message is written in this language. Defaults to `en`. |
| `relationship` | enum | yes | For cold leads this is `cold` (occasionally `warm` if there's a light prior touch). |
| `linkedin_url` | string (URL) | optional | Enables the LinkedIn channel and helps verification. |
| `last_interaction` | string \| null | optional | `null` for a true cold contact. |
| `known_priorities` | string[] | recommended | Personalisation hooks — the contact's current focus. Used to make relevance, not invented by the drafter. |

> **Minimum viable lead:** `lead_id`, `trigger.{type, summary, source_url, date, company}`,
> and `contact.{full_name, title, company, relationship}`. Everything else improves
> quality and confidence but is not blocking — missing optional fields lower the draft's
> confidence rather than breaking it.

---

## Shared inputs (from the credentials base, not per lead)

These match the existing `emerton_assets` / `style_reference` contracts already used by
the activation path (`data/samples/emerton_assets.json`). One set is reused for all leads.

```json
{
  "emerton_assets": {
    "relevant_offer": "Data strategy & AI value creation",
    "proof_points": ["One concrete, quantified result.", "..."],
    "sender": { "name": "...", "title": "...", "email": "..." },
    "credentials_url": "https://..."
  },
  "style_reference": {
    "tone": "professional, direct, warm, no salesy jargon",
    "past_messages": ["3–5 real past outreach messages to calibrate tone."]
  }
}
```

Ideally `relevant_offer` and `proof_points` are **matched to the trigger/sector** rather
than generic — a sector-relevant proof point is the single biggest quality lever. If the
assets base can return offer + proof points keyed by industry or trigger type, the cold
feeder will pass the best-matching set per lead.

---

## How it maps downstream

The cold feeder will turn each lead into a `DraftRequest` (see `src/bd_watch/schemas.py`):

- `trigger` → `Trigger`
- `contact` → `ContactProfile`, with `recipients = [full_name]` (cold leads are 1-to-1)
- shared `emerton_assets` → `EmertonAssets`, `style_reference` → `StyleReference`

Step 04 then produces one email + one LinkedIn message, validated against house style.

---

## Field conventions (please follow)

- Dates are ISO `YYYY-MM-DD`. Enums are lowercase exactly as listed (except seniority
  labels, which use the casing shown).
- `company` must be identical in `trigger` and `contact`.
- No fabrication upstream either: `summary`, `evidence`, and `known_priorities` must be
  grounded in the source. The drafter is told to use only provided facts, so anything
  invented here will surface in the message.
- Send dates/quotes in the source language is fine; the writing language is controlled
  solely by `contact.language`.

---

## Two sources, one contract

The cold path and the database-activation path are **two source adapters feeding one
internal contract**. Both normalise to a `DraftRequest` (trigger + contact + recipients
+ shared assets/style), so step 04 never special-cases the source. You do **not** need a
second internal contract — only a second adapter (the cold feeder), mirroring
`activation_feeder`.

What the two sources share:

- The **contact identity block** — `full_name`, `title`, `company`, `seniority`,
  `language` — is identical in shape.
- The **shared inputs** — `emerton_assets` and `style_reference` — are the same contract
  for both, pulled once from the credentials base.
- The **output** — one email + LinkedIn message(s), validated against house style.

Where they diverge:

| Dimension | Cold contact | Database activation |
|-----------|--------------|---------------------|
| Origin | Watch + Contact-ID teams | Our CRM deal export |
| Delivery | Batch of leads (`cold_leads_sample.json`) | `.xlsx` / `.csv` export (`Deal_Reminders…`) |
| `trigger.type` | `new_appointment`, `funding_round`, `press_article`, `new_regulation`, `event` | always `dormant_relationship` |
| `trigger.source_url` | Real public URL | Internal ref `crm://deal/N` |
| `trigger.summary` | The external event itself | Synthesized from CRM history (Days Since + Last Action + Recent Discussions) |
| `relationship` | `cold` (sometimes `warm`) | `dormant` / `existing_client`, by recency |
| `last_interaction` | `null` | Real last-contact date |
| Prior history | None — use `evidence` + `known_priorities` | Rich interaction history available |
| Recipients | Usually one person | May be several (shared email + 1-to-1 LinkedIn) |
| Default language | Per contact (`en`/`fr`) | `fr` (French accounts) |
| Salience | Editorial judgement of the event | Derived from the recency window |
| Trust | A claim about the outside world → needs verification | Trusted internal record |

In short: same destination, same contact block, same assets — different trigger origin,
relationship, and provenance. Each feeder's job is to absorb those differences so the
drafter sees a uniform request.

## Open questions for the other teams

Each question below carries our **proposed default** — adopt it unless you push back.

1. **Sector-matched assets?** Can the assets base return `relevant_offer` + `proof_points`
   keyed to the trigger/sector, or only a single global set?
   - *Proposed:* sector-keyed assets with a **global fallback**. The feeder asks for the
     best match by industry/trigger type and falls back to the global set when none
     exists. A sector-relevant proof point is the single biggest quality lever, so this is
     worth the extra structure; the fallback keeps it non-blocking.

2. **Batch or stream?** Will leads arrive as a batch file (like `cold_leads_sample.json`)
   or via a stream/endpoint?
   - *Proposed:* **batch JSON for the hackathon**, endpoint later. The feeder reads a path
     now (mirroring `activation_feeder`); we keep the JSON shape stable so swapping in an
     API client later is a localised change.

3. **Who owns dedup?** When the same appointment/article surfaces twice, who removes the
   duplicate?
   - *Proposed:* **Watch owns dedup at the source**, keyed on `lead_id` (and ideally a
     `(company, trigger.type, ~date)` signature). The feeder runs a **defensive second
     pass** on `lead_id` so a slip upstream never produces two messages to one person.
