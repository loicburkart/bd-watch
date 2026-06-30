"""Step 04 — Draft.

Draft a personalised email + LinkedIn message from the trigger, contact and assets.

Owner: [Sender Name]
Inputs:  DraftRequest
Outputs: OutreachDraft

Design notes
------------
- Adaptation rules (language, seniority, relationship) are computed from the request
  and injected into the system prompt, so one prompt covers every situation.
- The model returns structured JSON, which we then *independently* validate against
  the house style (word counts, single CTA, subject length). Validation can only
  lower confidence and add flags — it never trusts the model's self-report blindly.
  Step 05 relies on that: it auto-sends only when confidence is high and flags empty.
"""

from __future__ import annotations

import json
import logging
import re

try:
    import anthropic
except ImportError:  # keep the module importable without the SDK installed
    anthropic = None

from ..config import settings
from ..schemas import DraftRequest, Email, OutreachDraft

logger = logging.getLogger(__name__)

# House-style bounds — enforced after generation, not just requested in the prompt.
EMAIL_WORDS = (90, 130)
LINKEDIN_WORDS = (45, 75)
SUBJECT_MAX_CHARS = 60

MAX_TOKENS = 1024
TEMPERATURE = 0.7

_CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}
_RANK_CONFIDENCE = {v: k for k, v in _CONFIDENCE_RANK.items()}


# --------------------------------------------------------------------------- #
# Prompts
# --------------------------------------------------------------------------- #

SYSTEM_PROMPT = """\
You are Emerton's business-development outreach writer. Emerton is a strategy and data consulting firm.
Your job: write personalised first-contact messages that make people want to reply.

PRINCIPLES
1. The trigger is the reason the message exists. Always open on it — never on yourself or on Emerton.
2. Relevance before promotion. Show you understand the contact's challenge before mentioning Emerton.
3. One idea, one call-to-action. The goal is a reply, not a sale.
4. Brevity. Email: 90-130 words. LinkedIn: 45-75 words.
5. Credibility through proof, not adjectives. Cite one concrete proof point rather than "recognised leader".
6. Human tone. Write the way a senior partner writes to a peer: direct, respectful, zero flattery.

ADAPTATION GUIDELINES
{adaptation_rules}

DO NOT
- No empty superlatives ("must-have", "disruptive", "world leader").
- No flattery ("I admire your work").
- No paragraph about Emerton. One credibility sentence maximum.
- No attachment or link unless genuinely useful.
- No fabrication: use only the facts provided in the input. If something is missing, do not invent it.
- No clickbait or all-caps subject line.

OUTPUT
Respond ONLY with a valid JSON object with this exact shape:
{{
  "email": {{"subject": "...", "body": "...", "cta": "..."}},
  "linkedin": {{"message": "..."}},
  "rationale": "...",
  "confidence": "high | medium | low",
  "flags": []
}}
No text outside the JSON.
"""

INSTRUCTION_TEMPLATE = """\
Here are the elements. Write the email and the LinkedIn message.

# TRIGGER
{trigger_type} — {trigger_summary}
Source: {trigger_url} ({trigger_date})

# CONTACT
{contact_name}, {contact_title} @ {contact_company}
Relationship: {relationship} | Last interaction: {last_interaction}
Known priorities: {priorities}
Writing language: {language}

# EMERTON ASSETS
Relevant offer: {offer}
Available proof points: {proof_points}
Sender: {sender_name}, {sender_title}

# STYLE
Target tone: {tone}
Past examples to imitate:
{past_messages}

Produce the JSON.
"""


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _enum_value(x: object) -> str:
    """Return ``x.value`` for enums, otherwise ``str(x)``."""
    return getattr(x, "value", x) if not isinstance(x, str) else x


def _word_count(text: str) -> int:
    return len(text.split())


def _build_adaptation_rules(req: DraftRequest) -> str:
    """Turn the request context into explicit, situation-specific writing rules."""
    contact = req.contact
    rules = [f"- Write strictly in {contact.language.upper()}."]

    seniority = contact.seniority.lower()
    if seniority == "c-level":
        rules.append("- Register for C-level: highly concise, strategic, focused on bottom-line impact.")
    elif seniority == "vp":
        rules.append("- Register for VP: balance strategic objectives with operational scaling.")
    else:
        rules.append("- Register for management: focus on practical implementation and proven results.")

    rel = _enum_value(contact.relationship)
    if rel == "cold":
        rules.append("- Opening (cold): build quick legitimacy and give immediate value from the trigger.")
    elif rel == "warm":
        rules.append("- Opening (warm): include a light, natural reminder of the past connection.")
    elif rel == "dormant":
        when = contact.last_interaction or "some time ago"
        rules.append(f"- Opening (dormant): reconnect smoothly without guilt-tripping. Last contact: {when}.")
    elif rel == "existing_client":
        rules.append("- Opening (existing client): emphasise continuity; do not re-pitch who Emerton is.")

    return "\n".join(rules)


def _build_instruction(req: DraftRequest) -> str:
    contact = req.contact
    return INSTRUCTION_TEMPLATE.format(
        trigger_type=_enum_value(req.trigger.type),
        trigger_summary=req.trigger.summary,
        trigger_url=req.trigger.source_url,
        trigger_date=req.trigger.date,
        contact_name=contact.full_name,
        contact_title=contact.title,
        contact_company=contact.company,
        relationship=_enum_value(contact.relationship),
        last_interaction=contact.last_interaction or "n/a",
        priorities=", ".join(contact.known_priorities) or "n/a",
        language=contact.language,
        offer=req.assets.relevant_offer,
        proof_points=" | ".join(req.assets.proof_points),
        sender_name=req.assets.sender_name,
        sender_title=req.assets.sender_title,
        tone=req.style.tone,
        past_messages="\n".join(f"- {m}" for m in req.style.past_messages) or "- (none)",
    )


def _parse_llm_json(text: str) -> dict:
    """Extract the JSON object from a model response, tolerating prose / code fences."""
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in LLM response.")
    return json.loads(cleaned[start : end + 1])


def _cap_confidence(current: str, ceiling: str) -> str:
    """Return the lower of two confidence levels."""
    rank = min(_CONFIDENCE_RANK.get(current, 0), _CONFIDENCE_RANK[ceiling])
    return _RANK_CONFIDENCE[rank]


def _validate(draft: OutreachDraft) -> OutreachDraft:
    """Enforce house style. Adds flags and lowers confidence; never raises confidence."""
    flags = list(draft.flags)

    email_words = _word_count(draft.email.body)
    if not EMAIL_WORDS[0] <= email_words <= EMAIL_WORDS[1]:
        flags.append(f"email_length:{email_words}w")

    li_words = _word_count(draft.linkedin_message)
    if not LINKEDIN_WORDS[0] <= li_words <= LINKEDIN_WORDS[1]:
        flags.append(f"linkedin_length:{li_words}w")

    if len(draft.email.subject) > SUBJECT_MAX_CHARS:
        flags.append("subject_too_long")

    if not draft.email.cta.strip():
        flags.append("missing_cta")

    confidence = draft.confidence
    new_flags = [f for f in flags if f not in draft.flags]
    if new_flags:
        # One issue -> at most medium; two or more -> low.
        ceiling = "medium" if len(new_flags) == 1 else "low"
        confidence = _cap_confidence(confidence, ceiling)

    draft.flags = flags
    draft.confidence = confidence
    return draft


# --------------------------------------------------------------------------- #
# Main entry point
# --------------------------------------------------------------------------- #

def draft(req: DraftRequest) -> OutreachDraft:
    """Produce a validated email + LinkedIn message for the request."""
    if not settings.has_llm or anthropic is None:
        logger.warning("No ANTHROPIC_API_KEY or anthropic SDK; returning mock draft.")
        return _validate(_mock_draft(req))

    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        system = SYSTEM_PROMPT.format(adaptation_rules=_build_adaptation_rules(req))
        resp = client.messages.create(
            model=settings.model,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            system=system,
            messages=[{"role": "user", "content": _build_instruction(req)}],
        )
        out = _parse_llm_json(resp.content[0].text)
        email = out.get("email", {})
        generated = OutreachDraft(
            email=Email(
                subject=email.get("subject", ""),
                body=email.get("body", ""),
                cta=email.get("cta", ""),
            ),
            linkedin_message=out.get("linkedin", {}).get("message", ""),
            rationale=out.get("rationale", ""),
            confidence=out.get("confidence", "low"),
            flags=list(out.get("flags", [])),
        )
        return _validate(generated)
    except Exception:
        logger.exception("step04: LLM call or parsing failed; falling back to mock.")
        return _validate(_mock_draft(req))


def _mock_draft(req: DraftRequest) -> OutreachDraft:
    """Deterministic fallback when the API is unavailable or errors out.

    Always low confidence and flagged: a mock must never be eligible for auto-send.
    """
    name = req.contact.full_name.split()[0]
    return OutreachDraft(
        email=Email(
            subject="Congrats — plus a field note",
            body=(
                f"Hi {name},\n\nCongratulations on the news at {req.contact.company}. "
                f"The first few months often set the trajectory.\n\nWe recently helped a "
                f"similar player rework their approach — the kind of quick win that earns "
                f"credibility internally.\n\nWould you be open to a 15-minute "
                f"conversation?\n\nBest,\n{req.assets.sender_name} — {req.assets.sender_title}"
            ),
            cta="15-minute conversation about priorities.",
        ),
        linkedin_message=(
            f"Hi {name}, congratulations on the role at {req.contact.company}. "
            f"Happy to compare notes if it's a relevant moment."
        ),
        rationale="Mock output (API skipped or failed).",
        confidence="low",
        flags=["mock_output"],
    )
