#!/usr/bin/env python3
"""
Step 04 — Message Drafting | Hackathon demo
-------------------------------------------
Runs the drafting prompt on 3 sample triggers and prints an email +
LinkedIn message for each.

Usage:
    # Live mode (calls Claude — needs an API key):
    export ANTHROPIC_API_KEY=sk-ant-...
    python drafting_demo.py

    # Mock mode (no API key, prints baked-in sample outputs — safe for the demo):
    python drafting_demo.py --mock

Live mode requires:  pip install anthropic
"""

import argparse
import json
import os
import sys

MODEL = "claude-sonnet-4-6"

# --------------------------------------------------------------------------- #
# 1. PROMPTS
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
Respond ONLY with a valid JSON object with this exact shape:
{
  "email": {"subject": "...", "body": "...", "cta": "..."},
  "linkedin": {"message": "..."},
  "rationale": "...",
  "confidence": "high | medium | low",
  "flags": []
}
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


def build_instruction(case: dict) -> str:
    t, c, a, s = (
        case["trigger"],
        case["contact"],
        case["emerton_assets"],
        case["style_reference"],
    )
    return INSTRUCTION_TEMPLATE.format(
        trigger_type=t["type"],
        trigger_summary=t["summary"],
        trigger_url=t["source_url"],
        trigger_date=t["date"],
        contact_name=c["full_name"],
        contact_title=c["title"],
        contact_company=c["company"],
        relationship=c["relationship"],
        last_interaction=c["last_interaction"],
        priorities=", ".join(c["known_priorities"]),
        language=c["language"],
        offer=a["relevant_offer"],
        proof_points=" | ".join(a["proof_points"]),
        sender_name=a["sender"]["name"],
        sender_title=a["sender"]["title"],
        tone=s["tone"],
        past_messages="\n".join(f"- {m}" for m in s["past_messages"]),
    )


# --------------------------------------------------------------------------- #
# 2. SAMPLE INPUTS (mocked — would come from steps 1 & 3 + credentials base)
# --------------------------------------------------------------------------- #

SENDER = {"name": "[Sender Name]", "title": "[Sender Title], Emerton Data",
          "email": "sender@emerton-data.com"}

DEFAULT_STYLE = {
    "tone": "professional, direct, warm, no salesy jargon",
    "past_messages": [
        "Hi {name}, saw the news about {company} — congratulations. We've done similar work in your sector; happy to share a quick field note if useful.",
        "Hi {name}, it's been a while since we spoke. A recent project reminded me of your situation at {company} — worth a 15-minute catch-up?",
    ],
}

CASES = [
    {
        "label": "1 — New appointment (cold, C-level, EN)",
        "trigger": {
            "type": "new_appointment",
            "summary": "Marie Dupont has just been appointed Chief Data Officer of Acme Retail.",
            "source_url": "https://linkedin.com/posts/acme-retail-cdo",
            "date": "2026-06-28",
            "salience": "high",
        },
        "contact": {
            "full_name": "Marie Dupont", "title": "Chief Data Officer",
            "company": "Acme Retail", "seniority": "C-level", "language": "en",
            "relationship": "cold", "last_interaction": None,
            "known_priorities": ["data roadmap", "AI value creation"],
        },
        "emerton_assets": {
            "relevant_offer": "Data strategy & AI value creation",
            "proof_points": [
                "European retailer: +12% margin on the supply chain via a pricing model.",
                "Data practice of 40+ specialised consultants.",
            ],
            "sender": SENDER,
        },
        "style_reference": DEFAULT_STYLE,
    },
    {
        "label": "2 — Press article / funding (cold, VP, EN)",
        "trigger": {
            "type": "funding_round",
            "summary": "NovaPharma raised a EUR 80M Series C to scale its R&D data platform across Europe.",
            "source_url": "https://techpress.example/novapharma-series-c",
            "date": "2026-06-25",
            "salience": "high",
        },
        "contact": {
            "full_name": "James Okafor", "title": "VP Data & Analytics",
            "company": "NovaPharma", "seniority": "VP", "language": "en",
            "relationship": "cold", "last_interaction": None,
            "known_priorities": ["scaling data platform", "R&D analytics"],
        },
        "emerton_assets": {
            "relevant_offer": "Data platform scale-up & analytics operating model",
            "proof_points": [
                "Helped a life-sciences group cut data-product time-to-market by 40%.",
                "Dedicated healthcare & life-sciences data team.",
            ],
            "sender": SENDER,
        },
        "style_reference": DEFAULT_STYLE,
    },
    {
        "label": "3 — Dormant relationship (dormant, Director, FR)",
        "trigger": {
            "type": "dormant_relationship",
            "summary": "Sophie Lefèvre publie un article sur la gouvernance des données IA dans son secteur.",
            "source_url": "https://linkedin.com/posts/sophie-lefevre-ai-gov",
            "date": "2026-06-27",
            "salience": "medium",
        },
        "contact": {
            "full_name": "Sophie Lefèvre", "title": "Director of Data Governance",
            "company": "Banque Méridien", "seniority": "Director", "language": "fr",
            "relationship": "dormant", "last_interaction": "2025-01-15",
            "known_priorities": ["AI governance", "regulatory compliance"],
        },
        "emerton_assets": {
            "relevant_offer": "AI governance & regulatory readiness",
            "proof_points": [
                "Cadre de gouvernance IA déployé pour un acteur bancaire européen avant l'entrée en vigueur de l'AI Act.",
                "Practice mixte Data x Réglementaire.",
            ],
            "sender": SENDER,
        },
        "style_reference": DEFAULT_STYLE,
    },
]


# --------------------------------------------------------------------------- #
# 3. LIVE MODE — call Claude
# --------------------------------------------------------------------------- #

def run_live(case: dict) -> dict:
    from anthropic import Anthropic  # imported lazily so --mock needs no install

    client = Anthropic()  # reads ANTHROPIC_API_KEY from env
    resp = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_instruction(case)}],
    )
    text = resp.content[0].text.strip()
    # Be tolerant of stray prose around the JSON
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start : end + 1])


# --------------------------------------------------------------------------- #
# 4. MOCK MODE — baked-in outputs so the demo always works
# --------------------------------------------------------------------------- #

MOCK_OUTPUTS = [
    {
        "email": {
            "subject": "Congrats — plus a data/retail field note",
            "body": ("Hi Marie,\n\nCongratulations on your appointment as CDO of "
                     "Acme Retail. The first few months often set the data trajectory "
                     "for the years that follow.\n\nWe recently helped a European "
                     "retailer rework its supply-chain pricing — a 12% margin gain on "
                     "the relevant scope. The kind of quick win that earns a data "
                     "roadmap credibility internally.\n\nWould you be open to a "
                     "15-minute conversation about your priorities for the first 100 "
                     "days?\n\nBest,\n[Sender Name] — [Sender Title], Emerton Data"),
            "cta": "15-minute conversation about first-100-days priorities.",
        },
        "linkedin": {
            "message": ("Hi Marie, congratulations on the CDO role at Acme Retail. "
                        "At Emerton we work with retailers on data value creation — "
                        "recently a 12% supply-chain margin gain through pricing. "
                        "Happy to compare notes on your priorities if it's a relevant "
                        "moment."),
        },
        "rationale": ("Appointment angle: capitalises on the moment a new CDO is "
                      "building their roadmap. Quantified, sector-specific proof point."),
        "confidence": "high",
        "flags": [],
    },
    {
        "email": {
            "subject": "Scaling the platform after the Series C",
            "body": ("Hi James,\n\nCongratulations on NovaPharma's EUR 80M Series C — "
                     "scaling an R&D data platform across Europe is a different game "
                     "from building one.\n\nWe helped a life-sciences group cut "
                     "data-product time-to-market by 40% as they scaled, mostly by "
                     "fixing the operating model rather than the tech.\n\nWould a "
                     "20-minute exchange on what tends to break at this stage be "
                     "useful?\n\nBest,\n[Sender Name] — [Sender Title], Emerton Data"),
            "cta": "20-minute exchange on scaling pitfalls.",
        },
        "linkedin": {
            "message": ("Hi James, congratulations on NovaPharma's Series C. Scaling "
                        "an R&D data platform across Europe is where operating models "
                        "usually creak — we recently helped a life-sciences group cut "
                        "data-product time-to-market by 40%. Happy to share what we saw "
                        "if it's timely."),
        },
        "rationale": ("Funding angle: fresh capital means a scaling mandate. Proof "
                      "point targets the scaling pain, not the raise itself."),
        "confidence": "high",
        "flags": [],
    },
    {
        "email": {
            "subject": "Votre article sur la gouvernance IA",
            "body": ("Bonjour Sophie,\n\nJe viens de lire votre article sur la "
                     "gouvernance des données IA — votre point sur l'écart entre "
                     "principes et mise en œuvre résonne avec ce qu'on observe côté "
                     "bancaire.\n\nCela faisait un moment que nous n'avions pas "
                     "échangé. Nous avons depuis déployé un cadre de gouvernance IA "
                     "pour un acteur bancaire européen en amont de l'AI Act — sujet "
                     "proche du vôtre.\n\nUn échange de 15 minutes vous "
                     "intéresserait-il ?\n\nBien à vous,\n[Sender Name] — [Sender Title], "
                     "Emerton Data"),
            "cta": "Échange de 15 minutes sur la gouvernance IA.",
        },
        "linkedin": {
            "message": ("Bonjour Sophie, votre article sur la gouvernance IA m'a "
                        "interpellé, en particulier l'écart principes / mise en œuvre. "
                        "Cela faisait un moment — nous avons depuis déployé un cadre de "
                        "gouvernance IA pour une banque européenne avant l'AI Act. "
                        "Au plaisir de reprendre le fil si le sujet vous parle."),
        },
        "rationale": ("Dormant + content angle: the article is the natural reason to "
                      "reconnect. Light 'it's been a while' without guilt; proof point "
                      "matches her governance focus. Written in FR per contact."),
        "confidence": "high",
        "flags": [],
    },
]


def run_mock(index: int) -> dict:
    return MOCK_OUTPUTS[index]


# --------------------------------------------------------------------------- #
# 5. PRINTING
# --------------------------------------------------------------------------- #

def word_count(text: str) -> int:
    return len(text.split())


def print_result(case: dict, out: dict) -> None:
    line = "=" * 74
    print(f"\n{line}\nCASE {case['label']}\n{line}")
    print(f"TRIGGER : {case['trigger']['summary']}")
    print(f"CONTACT : {case['contact']['full_name']}, {case['contact']['title']} "
          f"@ {case['contact']['company']} "
          f"({case['contact']['relationship']}, {case['contact']['language']})")

    e = out["email"]
    print(f"\n--- EMAIL  [{word_count(e['body'])} words] ---")
    print(f"Subject: {e['subject']}")
    print(f"\n{e['body']}")

    li = out["linkedin"]["message"]
    print(f"\n--- LINKEDIN  [{word_count(li)} words] ---")
    print(li)

    print(f"\n--- REVIEW ---")
    print(f"Rationale : {out['rationale']}")
    print(f"Confidence: {out['confidence']}  |  Flags: {out['flags'] or 'none'}")


# --------------------------------------------------------------------------- #
# 6. MAIN
# --------------------------------------------------------------------------- #

def main() -> None:
    parser = argparse.ArgumentParser(description="Emerton Step 04 drafting demo")
    parser.add_argument("--mock", action="store_true",
                        help="Use baked-in outputs (no API key needed).")
    args = parser.parse_args()

    live = not args.mock and bool(os.environ.get("ANTHROPIC_API_KEY"))
    if not args.mock and not live:
        print("[i] No ANTHROPIC_API_KEY found — falling back to --mock mode.\n"
              "    Set the key and drop --mock for live generation.", file=sys.stderr)

    mode = "LIVE (Claude)" if live else "MOCK (baked-in)"
    print(f"Emerton — Step 04 Message Drafting | mode: {mode}")

    for i, case in enumerate(CASES):
        out = run_live(case) if live else run_mock(i)
        print_result(case, out)

    print(f"\n{'=' * 74}\nDone — {len(CASES)} triggers drafted.\n")


if __name__ == "__main__":
    main()
