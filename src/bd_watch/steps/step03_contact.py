"""Step 03 — Contact.

Identify the right contact at the company and build their profile.

Owner: TODO
Inputs:  QualifiedTrigger
Outputs: ContactProfile
"""

from __future__ import annotations

from ..schemas import ContactProfile, QualifiedTrigger, Relationship


def identify_contact(qt: QualifiedTrigger) -> ContactProfile:
    """Resolve the best contact for a qualified trigger.

    TODO: look up CRM + LinkedIn to find the decision-maker and enrich the profile.
    Returns a mock profile for now.
    """
    return ContactProfile(
        full_name="Marie Dupont",
        title="Chief Data Officer",
        company=qt.trigger.company,
        seniority="C-level",
        language="en",
        relationship=Relationship.COLD,
        linkedin_url="https://linkedin.com/in/marie-dupont",
        last_interaction=None,
        known_priorities=["data roadmap", "AI value creation"],
    )
