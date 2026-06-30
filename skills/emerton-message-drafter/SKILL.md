---
name: emerton-message-drafter
description: Draft Emerton business-development messages — one shared email plus one 1-to-1 LinkedIn message per contact — from an Excel of contacts, in Emerton's formal corporate register, grounded strictly in each row's facts and output email-ready. Handles three input shapes detected by columns: a CRM deal export of KNOWN clients for re-engagement (Interaction History, Days Since), a list of NEW prospects with an external trigger for cold outreach, and a LOST-deals post-mortem for re-engaging lost deals (Deal Info, Post-Mortem Context, Suggested Next Step). Output is a review-ready document, never auto-sent. Use whenever someone provides such an Excel and wants outreach emails and LinkedIn messages drafted. Triggers: "draft outreach", "write the emails", "relancer ces clients", "re-engage lost deals", "cold emails from this list".
---

# Emerton Message Drafter

The message-writing step of Emerton's BD pipeline: turn an Excel of contacts into review-ready
copy. For each contact, write one **email** and one **LinkedIn message**, in the right language,
in Emerton's formal register, grounded **strictly** in that row's facts. The output is a document
for human review before sending — this skill **never sends** anything.

## When to use

The user provides an Excel of contacts and wants outreach written. Three input shapes — detect by columns:

- **Known clients** — a CRM deal export (re-engagement / "activation"); has `Interaction History` / `Days Since`. Schema: `references/input_known_clients.md`.
- **New prospects** — newly identified leads with an external trigger (cold outreach). Schema: `references/input_new_prospects.md`.
- **Lost deals** — a lost-deal post-mortem (re-engage after a loss); has `Deal Info`, `Post-Mortem Context`, `Suggested Next Step`. Schema: `references/input_lost_deals.md`. **Never mention the loss; the post-mortem and next-step columns are internal and only set the angle.**

## Before drafting — ask the user once

1. **Sender** — the name and title to sign as (format: "<First Last>, <Title>, Emerton Data"). **Always ask for this at launch — there is no default sender.** Never hardcode, assume, or carry over a sender from a previous run, and never invent a name. The signature uses exactly the sender the user gives this run.
2. **Default language** — FR or EN, used when a row doesn't specify. (French accounts → FR; contacts clearly outside France → EN.)
3. **Output location** — where to save the review document.

Do not proceed without a sender supplied this run, and do not guess the language for a clearly-international contact. Until the sender is provided, leave the signature as the literal placeholder `[Sender Name] — [Sender Title]`.

## Workflow

1. **Read the Excel** (first sheet). Get clean rows with the helper:
   `python scripts/parse_deals.py <file.xlsx>` → normalised JSON. It detects the input type,
   skips placeholder/legend/empty rows, drops duplicate contacts, splits multi-person cells into
   recipients, and infers relationship + seniority.
2. **Draft per valid contact**, following `references/drafting_rules.md` — the binding spec
   (tone, perspective, no-fabrication rules, shared email + 1-to-1 LinkedIn, length, CTA, confidence).
3. **Triage, don't force:**
   - Skip rows with no real contact name (placeholder "—", legend/footer rows, `no_contact`).
   - **Very stale** deals (> 180 days) or **thin-data** rows (only "contact added") → still draft,
     but mark `confidence: low` and flag for human review. Keep them honest and generic; never invent a reason.
   - **Lost deals:** don't draft `archive_candidate` rows (P4 / "Archive") — list them under triage.
     For `hold_until_window` rows, draft but flag `hold_until:<date>`. Never mention the loss.
   - Note any duplicates you collapsed; list skipped/triaged rows in a short table at the end.
4. **Write a review document** (Markdown), grouped by contact, and save it to the agreed location.

## Output format (per contact) — must be email-ready

Each message goes in its **own fenced code block** so line breaks are preserved and the user can
copy-paste it straight into an email/LinkedIn. **Never run the subject, greeting, body, CTA and
signature together in one paragraph.** Lay them out as a real email: subject line, blank line,
greeting, blank line, one or two short paragraphs, blank line, the CTA as its own closing line,
blank line, signature.

````
### <Company> — <Contact name(s)>
**Relationship:** <cold|warm|dormant|existing_client> · **Language:** <fr|en> · **Context:** <one line; for lost deals, the safe hook only>

**Email** — _subject: <≤60 chars, factual>_

```text
Bonjour <Prénom>,            ← "Hi <First>," in EN

<paragraph 1 — opens on the contact/trigger>

<paragraph 2 — relevance, then at most one Emerton sentence>

<CTA — a single clear ask, on its own line>

Bien à vous,                 ← "Best," in EN
<Sender name> — <Sender title>
```

**LinkedIn — <recipient name>**

```text
<45–75 EN / 40–70 FR words, distinct from the email>
```

**Review:** confidence: <high|medium|low> · flags: <very_stale, thin_data, language_assumed, hold_until:<date>, addressee_review, none>
````

Body length: EN email 90–130 / FR 80–120 words; the signature is shown in the block but is **not**
counted toward the body length. One shared email per row (greeting all recipients); one separate
LinkedIn block per recipient.

## Non-negotiable rules (full version in references/drafting_rules.md)

- Use **only** facts present in the row. **Never invent** a figure, percentage, result, client name, or
  meeting. With no grounded number, make the point qualitatively or omit it.
- The interaction history is **Emerton's internal record** (our perspective). Never attribute our meetings,
  colleagues, or internal steps to the contact; reference only what the row says the contact did. A proposal
  "sent internally" has **not** been sent to the client.
- **One shared email** to all named recipients; **one separate LinkedIn message per recipient** (1-to-1, never a group note, never copy-pasted from the email).
- Formal, corporate register — vouvoiement in French. No effusive openers ("ravi"), no exclamation marks,
  no sales clichés ("aucune pression", "quick win"). Open on the contact/trigger, never on Emerton.
- Write in the contact's language; if unknown and the contact is clearly international, use English.
- Never auto-send. Every draft is for human review.
