---
name: emerton-outreach-drafter
description: Draft personalised business-development outreach (a shared email plus one 1-to-1 LinkedIn message per contact) from an Excel file of contacts, in Emerton's formal corporate style. Handles two input types — a CRM deal export of KNOWN clients (columns such as Company, Contact, Scope of Discussion, Last Action, Days Since, Interaction History) and a list of NEW prospects/leads (an external trigger plus a contact). Use whenever someone provides such an Excel and wants outreach emails and LinkedIn messages drafted and reviewed. Triggers: "draft outreach", "réactiver mes contacts", "relancer ces clients", "cold emails from this list".
---

# Emerton Outreach Drafter

Turn an Excel of contacts into review-ready outreach: for each contact, one **email** and one **LinkedIn message**, in the right language, grounded strictly in the row's facts, in Emerton's formal register. The output is for human review before sending — never auto-send.

## When to use

The user provides an Excel and wants outreach drafted. Two input shapes (detect by columns):

- **Known clients** — a CRM deal export (re-engagement / "activation"). Schema: `references/input_known_clients.md`.
- **New prospects** — newly identified leads with an external trigger (cold outreach). Schema: `references/input_new_prospects.md`.

## Before drafting — ask the user (once)

1. **Sender** — name and title to sign as (e.g. "Ugo Martin, Partner, Emerton Data"). Required for the signature.
2. **Default language** — FR or EN, used when a row doesn't specify one. (Known-client French accounts → FR; international contacts → EN. If a row's contact is clearly outside France, write in English.)
3. **Output location** — where to save the review file.

Do not proceed with a placeholder sender or guessed language for clearly-international contacts.

## Workflow

1. **Read the Excel** (first sheet). Optionally run the helper to get clean rows:
   `python scripts/parse_deals.py <file.xlsx>` → prints normalised JSON (skips placeholder/legend/empty rows, drops duplicate contacts, infers relationship and seniority, and labels which input type it detected).
2. **Per valid contact, draft** following `references/drafting_rules.md` — that file is the binding spec (tone, perspective, the no-fabrication rules, shared email + 1-to-1 LinkedIn, length, CTA, confidence).
3. **Triage, don't force:**
   - Skip rows with no real contact name (placeholder "—", legend/footer rows).
   - For **very stale** deals (> 180 days since contact) or **thin-data** rows (only "contact added"), still draft but mark `confidence: low` and flag for human review — keep them honest and generic, never invent a reason.
   - Note duplicates you collapsed.
4. **Write a review document** (Markdown) grouped by contact and save it.

## Output format (per contact)

```
## <Company> — <Contact name(s)>
- Relationship: <cold|warm|dormant|existing_client> · Language: <fr|en> · Last contact: <date|n/a>
- Context (from the row): <one line>

**Email — subject:** <≤60 chars, factual>
<body, ~90–130 words, formal; system/you append the signature>
_CTA: <single clear ask>_

**LinkedIn** (one per recipient, 1-to-1):
_To <name>:_ <45–75 words, distinct from the email>

**Review:** confidence: <high|medium|low> · flags: <e.g. very_stale, thin_data, language_assumed, duplicate_collapsed, none>
```

## Non-negotiable rules (full version in references/drafting_rules.md)

- Use **only** facts present in the row. **Never invent** a figure, percentage, result, client name, or meeting. If you have no grounded number, make the point qualitatively or omit it.
- The interaction history is **Emerton's internal record** (our perspective). Never attribute our meetings, colleagues, or steps to the contact; reference only what the row explicitly says the contact did.
- **One shared email** addressed to all named recipients; **one separate LinkedIn message per recipient** (LinkedIn is 1-to-1, never a group note).
- Formal, corporate register — vouvoiement in French. No effusive openers ("ravi"), no exclamation marks, no sales clichés ("aucune pression", "quick win").
- Write in the contact's language; if unknown and the contact is clearly international, use English.
