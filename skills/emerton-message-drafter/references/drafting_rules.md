# Drafting rules (binding spec)

The drafter's job: from one contact's row, write a short email + a short LinkedIn message
that make a senior person want to reply. Emerton is a top-tier strategy & data/AI
consulting firm — write accordingly.

## Principles

1. **Open on the reason.** The first sentence is about the contact's situation or the
   triggering event — never about Emerton or yourself.
2. **Relevance before promotion.** Show you understand their context before any mention
   of Emerton (one sentence of Emerton context, maximum).
3. **One idea, one call-to-action.** The goal is a reply, not a sale.
4. **Brevity (language-aware).** French prose is denser than English, so the same substance
   lands shorter — use per-language bands rather than one English-centric range:
   - **EN** — email 90–130 words; LinkedIn 45–75 words.
   - **FR** — email 80–120 words; LinkedIn 40–70 words.
   Count the body only (the signature is appended separately). Hitting the band is a *check*,
   not a goal: never pad with filler to reach a minimum — tighten, or if genuinely thin, flag it.
5. **Credibility through relevance, not name-dropping.** Do NOT cite specific client
   names, results, metrics, or figures — you are given none and must invent none.
   Credibility comes from understanding their situation, plus at most one general
   sentence about Emerton's domain. No quantified claims.
6. **Register.** Formal, precise, corporate, measured — a senior partner writing to a
   senior executive. French uses vouvoiement and formal salutations
   ("Bonjour Madame X," / "Bonjour Monsieur Y,"). Never casual, effusive, or salesy.
7. **Perspective & factual accuracy (most important).** For known clients, the
   interaction history is Emerton's INTERNAL CRM record, written from our side. Our
   meetings, our colleagues, our deck sends, our internal proposal drafts are OUR
   actions. Never imply the recipient performed, attended, requested, or even knows
   about an internal step. Reference only what the row explicitly attributes to the
   recipient ("your message of 12 June", "the presentation you attended"). When
   ownership is unclear, omit. A proposal "sent internally" has NOT been sent to them.
8. **Channels.** One shared email greeting all named recipients together; one distinct
   1-to-1 LinkedIn message per recipient. Never reuse the same text; never put one
   person's words in another's message.

## Hard "do not"

- Never state a number, percentage, monetary amount, or metric that is not present
  verbatim in the row. Invent no figures.
- Never present any result as the recipient's own, nor imply Emerton already delivered
  something for them, unless the row explicitly says so.
- No effusive openers ("ravi", "super", "j'espère que vous allez bien"), no exclamation
  marks, no sales clichés ("aucune pression de notre part", "au plaisir", "quick win").
- No clickbait or all-caps subject line. Subject ≤ 60 characters, factual.
- No closing signature inside the body — append it separately as
  `Bien à vous,\n<Sender name> — <Sender title>` (FR) or `Best,\n…` (EN).

## Format — email-ready (not one block)

Output each message in its own fenced code block, laid out like a real email so it can be
copy-pasted directly: **subject** line, blank line, **greeting**, blank line, **one or two short
paragraphs**, blank line, the **CTA** as its own closing line, blank line, **signature**. Never
collapse subject + greeting + body + CTA + signature into a single paragraph. LinkedIn goes in a
separate block. (Counting words for the length check excludes the signature.)

## Relationship-specific opening

- **cold** → establish quick legitimacy and immediate relevance from the trigger.
- **warm** → a light, natural reminder of the prior connection.
- **dormant** → reconnect smoothly without guilt-tripping; reference the real last step.
- **existing_client** → continuity, no re-pitch of who Emerton is.
- **lost deal** (dormant + `deal_status: lost`) → re-open **without ever mentioning the loss**.
  Open on a forward-looking hook (a development in the field, an adjacent active programme, a
  neutral check-in). Use `Suggested Next Step` only as the *angle* — never quote it, never reveal
  the strategy. **Never** cite the deal amount, the lost date, the loss reason, competitor guesses,
  internal colleague names, or phone numbers from the post-mortem. If the next step names a
  different addressee than the row's contact, draft to the contact and flag `addressee_review`.

## Self-check before finalising (rewrite if any fail)

- First sentence is about the contact/trigger, not Emerton.
- Length within the language band (EN: email 90–130 / LinkedIn 45–75; FR: email 80–120 / LinkedIn 40–70).
- Exactly one CTA.
- No figure/metric that isn't in the row. No invented facts.
- No internal Emerton step attributed to the recipient.
- For lost deals: no mention of the loss/rejection/date/amount; no internal context leaked.
- Email is laid out email-ready (subject, greeting, paragraphs, CTA, signature on separate lines).
- Language = the contact's language. Formal register, vouvoiement (FR).
- Subject ≤ 60 chars, factual.

## Confidence & flags (for the review line)

- `high` — rich, specific row context; message is well grounded.
- `medium` — usable but thin context, or language had to be assumed.
- `low` — very stale (> 180 days), almost no history, or anything you had to keep generic.
  Low-confidence items are for human review, not sending.
- Flags: `very_stale`, `thin_data`, `language_assumed`, `duplicate_collapsed`,
  `missing_company`, `no_contact_name`, `hold_until:<date>`, `addressee_review`,
  `bundle_only`, `archive_candidate`, etc.

## Mini examples

**Bad (invented + mis-attributed):**
> "Ravi que votre échange avec Gilles se soit bien passé ! Nous avons généré +12 % de
> marge via l'optimisation de votre modèle tarifaire."
Problems: effusive + "!"; the Gilles meeting was Emerton's, not the contact's; "+12 %"
and "votre modèle tarifaire" are invented and attributed to the recipient.

**Good (grounded + formal):**
> "Bonjour Catherine, je fais suite à votre message du 12 juin concernant la suite de
> notre présentation du 27 mai. Nous avons depuis pu échanger avec Gilles ; l'étape
> restante porte sur l'alignement des équipes R&D. Seriez-vous disponible pour un point
> de quinze minutes dans les prochains jours ?"
