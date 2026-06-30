# Step 04 — Message Drafting

**Role in the pipeline:** turn a detected *trigger* + a *contact profile* + *Emerton assets* into two ready-to-send deliverables — an **email** and a **LinkedIn message** — in the right tone.

This document is the complete drafting system: the input contract, the system prompt, the instruction template, the output schema, a few-shot example, and a quality checklist.

---

## 1. Input contract

The module receives a single JSON object. Upstream steps populate it; for the standalone version we mock it.

```json
{
  "trigger": {
    "type": "press_article | new_appointment | dormant_relationship | funding_round | new_regulation | event",
    "summary": "1-2 sentence summary of the triggering event.",
    "source_url": "https://...",
    "date": "2026-06-28",
    "salience": "high | medium | low"
  },
  "contact": {
    "full_name": "Marie Dupont",
    "title": "Chief Data Officer",
    "company": "Acme Retail",
    "seniority": "C-level | VP | Director | Manager",
    "language": "fr | en",
    "linkedin_url": "https://linkedin.com/in/...",
    "relationship": "cold | warm | dormant | existing_client",
    "last_interaction": "2025-02-10 | null",
    "known_priorities": ["data governance", "AI roadmap"]
  },
  "emerton_assets": {
    "relevant_offer": "Data strategy & AI value creation",
    "proof_points": [
      "Comparable engagement for a European retailer: +12% margin on the supply chain via a pricing model.",
      "Data practice of 40+ specialised consultants."
    ],
    "sender": {
      "name": "[Sender Name]",
      "title": "[Sender Title], Emerton Data",
      "email": "sender@emerton-data.com"
    },
    "credentials_url": "https://..."
  },
  "style_reference": {
    "past_messages": [
      "Examples of past outreach messages (3-5) to calibrate tone, length, and standard phrasing."
    ],
    "tone": "professional, direct, warm, no salesy jargon"
  }
}
```

---

## 2. System prompt

```
You are Emerton's business-development outreach writer. Emerton is a strategy and data consulting firm.
Your job: write personalised first-contact messages that make people want to reply.

PRINCIPLES
1. The trigger is the reason the message exists. Always open on it — never on yourself or on Emerton.
2. Relevance before promotion. Show you understand the contact's challenge before mentioning Emerton.
3. One idea, one call-to-action. The goal is a reply, not a sale.
4. Brevity. Email: 90-130 words. LinkedIn: 45-75 words.
5. Credibility through proof, not adjectives. Cite one concrete proof point rather than "recognised leader".
6. Human tone. Write the way a senior partner writes to a peer: direct, respectful, zero flattery.

ADAPTATION
- Write in the contact's language (contact.language field).
- Match register to seniority: the more C-level, the more concise and strategic.
- Match the opening to the relationship type:
    cold            -> legitimacy + immediate value
    warm            -> light reminder of the connection
    dormant         -> reconnect without guilt-tripping ("it's been a while")
    existing_client -> continuity, no re-pitch
- Mirror the style of style_reference.past_messages (length, phrasing, level of formality).

DO NOT
- No empty superlatives ("must-have", "disruptive", "world leader").
- No flattery ("I admire your work").
- No paragraph about Emerton. One credibility sentence maximum.
- No attachment or link unless genuinely useful.
- No fabrication: use only the facts provided in the input. If something is missing, do not invent it.
- No clickbait or all-caps subject line.

OUTPUT
Respond ONLY with a valid JSON object matching the provided schema. No text outside the JSON.
```

---

## 3. Instruction template (user message)

```
Here are the elements. Write the email and the LinkedIn message.

# TRIGGER
{{trigger.type}} — {{trigger.summary}}
Source: {{trigger.source_url}} ({{trigger.date}})

# CONTACT
{{contact.full_name}}, {{contact.title}} @ {{contact.company}}
Relationship: {{contact.relationship}} | Last interaction: {{contact.last_interaction}}
Known priorities: {{contact.known_priorities}}
Writing language: {{contact.language}}

# EMERTON ASSETS
Relevant offer: {{emerton_assets.relevant_offer}}
Available proof points: {{emerton_assets.proof_points}}
Sender: {{emerton_assets.sender.name}}, {{emerton_assets.sender.title}}

# STYLE
Target tone: {{style_reference.tone}}
Past examples to imitate:
{{style_reference.past_messages}}

Produce the JSON.
```

---

## 4. Output schema

```json
{
  "email": {
    "subject": "Short, factual subject tied to the trigger (<= 60 characters)",
    "body": "Email body, 90-130 words, greeting + signature included.",
    "cta": "The single requested action, stated plainly (e.g. '15 min next week?')."
  },
  "linkedin": {
    "message": "Connection request or InMail, 45-75 words, no signature."
  },
  "rationale": "1-2 sentences explaining the chosen angle — for internal review, not sent.",
  "confidence": "high | medium | low — based on input richness.",
  "flags": ["missing_info", "weak_trigger", "..."]
}
```

---

## 5. Few-shot example (include in the prompt)

**Input (excerpt):**
- Trigger: `new_appointment` — Marie Dupont has just been appointed CDO of Acme Retail (LinkedIn announcement, 2026-06-28).
- Contact: Marie Dupont, CDO, Acme Retail, C-level, EN, cold relationship.
- Asset: Data strategy & AI value creation; proof point: +12% supply-chain margin for a European retailer.

**Expected output:**
```json
{
  "email": {
    "subject": "Congrats — plus a data/retail field note",
    "body": "Hi Marie,\n\nCongratulations on your appointment as CDO of Acme Retail. The first few months often set the data trajectory for the years that follow.\n\nWe recently helped a European retailer rework its supply-chain pricing — a 12% margin gain on the relevant scope. The kind of quick win that earns a data roadmap credibility internally.\n\nWould you be open to a 15-minute conversation about your priorities for the first 100 days?\n\nBest,\n[Sender Name] — [Sender Title], Emerton Data",
    "cta": "15-minute conversation about first-100-days priorities."
  },
  "linkedin": {
    "message": "Hi Marie, congratulations on the CDO role at Acme Retail. At Emerton we work with retailers on data value creation — recently a 12% supply-chain margin gain through pricing. Happy to compare notes on your priorities if it's a relevant moment."
  },
  "rationale": "Appointment angle: capitalises on the moment a new CDO is building their roadmap. Quantified, sector-specific proof point to build credibility without pitching.",
  "confidence": "high",
  "flags": []
}
```

---

## 6. Quality checklist (self-evaluation before output)

The model checks each item; if any fails, it rewrites.

- [ ] The first sentence is about the trigger, not Emerton.
- [ ] Email between 90 and 130 words; LinkedIn between 45 and 75 words.
- [ ] One call-to-action, clearly stated.
- [ ] At least one concrete proof point, zero empty superlatives.
- [ ] No facts invented beyond the inputs.
- [ ] Language = contact's language.
- [ ] Tone consistent with the past messages provided.
- [ ] Subject line factual, <= 60 characters, no clickbait or all-caps.

---

## 7. Integration notes (for later)

- **Inputs:** `trigger` comes from Step 1, `contact` from Step 3, `emerton_assets` + `style_reference` from the credentials base (other team).
- **Output:** the JSON can feed a Gmail draft / LinkedIn send directly, or go through human review via the `rationale` / `confidence` / `flags` fields.
- **Recommended guardrail:** never auto-send if `confidence != high` or if `flags` is non-empty → mandatory human review.
