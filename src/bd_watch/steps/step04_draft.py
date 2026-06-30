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
from ..schemas import DraftRequest, Email, LinkedInDraft, OutreachDraft

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
5. Credibility through relevance, not name-dropping. Do NOT cite specific client names, results, metrics, or figures — none are provided to you and you must invent none. Establish credibility only by showing you understand the contact's situation, plus at most one general sentence about Emerton's domain (strategy and data/AI consulting). No quantified claims.
6. Register. Emerton is a top-tier strategy & data consulting firm; write accordingly. Formal, precise, corporate, restrained. The tone of a senior partner addressing a senior executive — never casual, effusive, or salesy. In French, use vouvoiement throughout and formal salutations ("Bonjour Madame X," / "Bonjour Monsieur Y,").
7. Perspective & factual accuracy. The interaction history is Emerton's INTERNAL CRM record, written from our side. Internal steps — our meetings, our colleagues (e.g. the Emerton account owner), our deck sends, our follow-ups, our internal proposal drafts — are OUR actions. Never imply the recipient performed, attended, requested, or is even aware of an internal step. Reference only what the input explicitly attributes to the recipient (e.g. "your message of 12 June", "the presentation you attended"). When ownership of an action is unclear, omit it rather than guess. A proposal "sent internally" has NOT been sent to the client.
8. LinkedIn vs Email: LinkedIn is a distinct channel — shorter and self-contained. Do not copy-paste the email.
9. Multiple recipients: the email is ONE shared message greeting all named recipients together. LinkedIn is strictly 1-to-1 — write a separate, distinct message for each recipient (do not reuse the same text). Do not attribute one recipient's statements or actions to another.

ADAPTATION GUIDELINES
{adaptation_rules}

DO NOT
- No empty superlatives ("must-have", "disruptive", "world leader").
- No flattery ("I admire your work") and no effusive openers ("ravi", "super", "j'espère que vous allez bien"). No exclamation marks.
- No casual or breezy phrasing, no sales clichés ("aucune pression de notre part", "au plaisir d'échanger", "quick win"). Stay measured and executive.
- No paragraph about Emerton. One credibility sentence maximum.
- No attachment or link unless genuinely useful.
- No fabrication: use only facts in the input. In particular, do NOT attribute to the recipient any meeting, action, request, statement, or knowledge that the input does not explicitly attribute to them (see principle 7). When in doubt, omit.
- Never present a proof point as the recipient's own result, and never imply Emerton has already delivered it for them or their company.
- Never state a number, percentage, metric, or monetary figure that is not present verbatim in the provided inputs. Invent no figures; if you have no grounded figure, make the point qualitatively or omit it.
- No clickbait or all-caps subject line.
- Do NOT include a closing signature in the email body (do not append "Best, Name - Company" or similar). The system will add it automatically!

OUTPUT
Respond ONLY with a valid JSON object with this exact shape:
{{
  "email": {{"subject": "...", "body": "...", "cta": "..."}},
  "linkedin": [{{"recipient": "<exact recipient name>", "message": "..."}}],
  "rationale": "...",
  "confidence": "high | medium | low",
  "flags": []
}}
The "linkedin" array must contain exactly one entry per recipient listed in the input,
using the recipient's exact name. No text outside the JSON.
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
Recipients (email greets all together; one LinkedIn message each): {recipients}

# SENDER (for the signature voice; do not add a signature — the system appends it)
{sender_name}, {sender_title}

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
        recipients=", ".join(req.recipients) or contact.full_name,
        sender_name=req.assets.sender_name,
        sender_title=req.assets.sender_title,
        tone=req.style.tone,
        past_messages="\n".join(f"- {m}" for m in req.style.past_messages) or "- (none)",
    )


def _first_name(full_name: str) -> str:
    parts = full_name.strip().split()
    return parts[0] if parts else full_name.strip()


def _greeting(recipients: list[str], language: str) -> str:
    """Shared email greeting addressing all recipients by first name."""
    names = ", ".join(_first_name(r) for r in recipients if r.strip())
    if language.lower() == "fr":
        return f"Bonjour {names}," if names else "Bonjour,"
    return f"Hi {names}," if names else "Hi,"


def _parse_linkedin(raw: object, recipients: list[str]) -> list[LinkedInDraft]:
    """Normalise the model's ``linkedin`` field into one draft per recipient.

    Tolerates a list of objects, a single object, or a bare string.
    """
    items: list[dict] = []
    if isinstance(raw, list):
        items = [x for x in raw if isinstance(x, dict)]
    elif isinstance(raw, dict):
        items = [raw]
    elif isinstance(raw, str):
        items = [{"recipient": recipients[0] if recipients else "", "message": raw}]

    drafts = [
        LinkedInDraft(recipient=str(i.get("recipient", "")).strip(), message=str(i.get("message", "")).strip())
        for i in items
        if i.get("message")
    ]
    return drafts or [LinkedInDraft(recipient=r, message="") for r in recipients]


def _parse_llm_json(text: str) -> dict:
    """Extract the JSON object from a model response, tolerating prose / code fences."""
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    start = cleaned.find("{")
    if start == -1:
        raise ValueError("No JSON object found in LLM response.")
    
    decoder = json.JSONDecoder()
    try:
        obj, _ = decoder.raw_decode(cleaned[start:])
        return obj
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON: {e}")



def _cap_confidence(current: str, ceiling: str) -> str:
    """Return the lower of two confidence levels."""
    rank = min(_CONFIDENCE_RANK.get(current, 0), _CONFIDENCE_RANK[ceiling])
    return _RANK_CONFIDENCE[rank]


# Quantified claims (percentages and monetary/magnitude figures) — the kinds of numbers
# that constitute a factual assertion. Dates, durations ("15 minutes") are ignored.
_PCT_RE = re.compile(r"(\d{1,3}(?:[.,]\d+)?)\s?%")
# Monetary / magnitude figures, in either order: "€80M", "EUR 80M", "80 M€", "80 millions".
_CUR_RE = re.compile(
    r"(?:€|eur|usd|\$)\s?(\d[\d.,]*)"
    r"|(\d[\d.,]*)\s?(?:k€|m€|bn€|milliards?|millions?|k|m|bn|md|€|eur|usd|\$)\b",
    re.IGNORECASE,
)


def _claim_numbers(text: str) -> set[str]:
    """Extract normalised percentage and monetary figures from text.

    Targets quantified *claims* (percentages, monetary amounts). Ignores durations
    ("15 minutes") and years, which are not assertions of fact about results.
    """
    nums: set[str] = set()
    for m in _PCT_RE.finditer(text or ""):
        nums.add(m.group(1).replace(" ", "").replace(",", ".").rstrip("."))
    for m in _CUR_RE.finditer(text or ""):
        num = m.group(1) or m.group(2)
        if num:
            nums.add(num.replace(" ", "").replace(",", ".").rstrip("."))
    return nums


def _input_metrics(req: DraftRequest) -> set[str]:
    """All quantified figures that legitimately appear in the inputs for this request."""
    text = " ".join(
        [
            req.trigger.summary,
            " ".join(req.contact.known_priorities),
            req.contact.last_interaction or "",
        ]
    )
    return _claim_numbers(text)


def _validate(draft: OutreachDraft, allowed_metrics: set[str] | None = None) -> OutreachDraft:
    """Enforce house style. Adds flags and lowers confidence; never raises confidence.

    If ``allowed_metrics`` is provided, any percentage/monetary figure appearing in the
    output but not in that set is flagged as ungrounded (likely fabricated).
    """
    flags = list(draft.flags)
    fabricated_metric = False

    email_words = _word_count(draft.email.body)
    if not EMAIL_WORDS[0] <= email_words <= EMAIL_WORDS[1]:
        flags.append(f"email_length:{email_words}w")

    if not draft.linkedin:
        flags.append("missing_linkedin")
    for li in draft.linkedin:
        li_words = _word_count(li.message)
        if not LINKEDIN_WORDS[0] <= li_words <= LINKEDIN_WORDS[1]:
            flags.append(f"linkedin_length[{li.recipient}]:{li_words}w")

    if len(draft.email.subject) > SUBJECT_MAX_CHARS:
        flags.append("subject_too_long")

    if not draft.email.cta.strip():
        flags.append("missing_cta")

    if allowed_metrics is not None:
        output_text = draft.email.body + " " + " ".join(li.message for li in draft.linkedin)
        ungrounded = _claim_numbers(output_text) - allowed_metrics
        for n in sorted(ungrounded):
            flags.append(f"ungrounded_metric:{n}")
            fabricated_metric = True

    confidence = draft.confidence
    new_flags = [f for f in flags if f not in draft.flags]
    if new_flags:
        # One issue -> at most medium; two or more -> low. A fabricated figure is
        # serious on its own -> force low.
        ceiling = "low" if (fabricated_metric or len(new_flags) >= 2) else "medium"
        confidence = _cap_confidence(confidence, ceiling)

    draft.flags = flags
    draft.confidence = confidence
    return draft


# --------------------------------------------------------------------------- #
# Main entry point
# --------------------------------------------------------------------------- #

def _call_databricks(system: str, instruction: str) -> str:
    """Call a Databricks serving endpoint (OpenAI-compatible chat completions)."""
    from openai import OpenAI

    host = settings.databricks_host.rstrip("/")
    client = OpenAI(api_key=settings.databricks_token, base_url=f"{host}/serving-endpoints")
    resp = client.chat.completions.create(
        model=settings.databricks_endpoint,
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": instruction},
        ],
    )
    return resp.choices[0].message.content or ""


def _call_anthropic(system: str, instruction: str) -> str:
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    resp = client.messages.create(
        model=settings.model,
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
        system=system,
        messages=[{"role": "user", "content": instruction}],
    )
    return resp.content[0].text


def _assemble(out: dict, req: DraftRequest) -> OutreachDraft:
    """Turn parsed model JSON into a validated OutreachDraft (signature appended)."""
    email = out.get("email", {})
    signoff = "Bien à vous," if req.contact.language.lower() == "fr" else "Best,"
    body = f"{email.get('body', '')}\n\n{signoff}\n{req.assets.sender_name} — {req.assets.sender_title}"
    generated = OutreachDraft(
        email=Email(subject=email.get("subject", ""), body=body, cta=email.get("cta", "")),
        linkedin=_parse_linkedin(out.get("linkedin"), req.recipients),
        rationale=out.get("rationale", ""),
        confidence=out.get("confidence", "low"),
        flags=list(out.get("flags", [])),
    )
    return _validate(generated, _input_metrics(req))


def draft(req: DraftRequest) -> OutreachDraft:
    """Produce a validated email + LinkedIn message for the request.

    Provider priority: Databricks serving endpoint -> Anthropic API -> mock fallback.
    """
    system = SYSTEM_PROMPT.format(adaptation_rules=_build_adaptation_rules(req))
    instruction = _build_instruction(req)

    if settings.has_databricks:
        provider = "databricks"
    elif settings.has_llm and anthropic is not None:
        provider = "anthropic"
    else:
        logger.warning("No LLM backend configured (Databricks or Anthropic); returning mock draft.")
        return _validate(_mock_draft(req))

    try:
        text = _call_databricks(system, instruction) if provider == "databricks" else _call_anthropic(system, instruction)
        return _assemble(_parse_llm_json(text), req)
    except Exception:
        logger.exception("step04: %s call or parsing failed; falling back to mock.", provider)
        return _validate(_mock_draft(req))


def _mock_draft(req: DraftRequest) -> OutreachDraft:
    """Deterministic fallback when the API is unavailable or errors out.

    One shared email greeting all recipients + one LinkedIn message per recipient.
    Always low confidence and flagged: a mock must never be eligible for auto-send.
    """
    lang = req.contact.language.lower()
    company = req.contact.company
    greeting = _greeting(req.recipients, lang)

    if lang == "fr":
        body = (
            f"{greeting}\n\nPour faire suite à nos échanges concernant {company} — un point "
            f"rapide pourrait nous aider à débloquer la suite.\n\nBien à vous,\n"
            f"{req.assets.sender_name} — {req.assets.sender_title}"
        )
        cta = "Un point de 15 minutes ?"
        li = "Bonjour {first}, pour faire suite à nos échanges chez {company} — au plaisir d'en reparler si le moment est opportun."
    else:
        body = (
            f"{greeting}\n\nFollowing up on our conversations about {company} — a short "
            f"call could help us unblock the next step.\n\nBest,\n"
            f"{req.assets.sender_name} — {req.assets.sender_title}"
        )
        cta = "A 15-minute call?"
        li = "Hi {first}, following up on our conversations at {company} — happy to pick this back up if the timing works."

    linkedin = [
        LinkedInDraft(recipient=name, message=li.format(first=_first_name(name), company=company))
        for name in req.recipients
    ]
    return OutreachDraft(
        email=Email(subject="Suite à nos échanges", body=body, cta=cta),
        linkedin=linkedin,
        rationale="Mock output (API skipped or failed).",
        confidence="low",
        flags=["mock_output"],
    )
