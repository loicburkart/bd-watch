"""Shared data contracts that flow between pipeline steps.

These are the interfaces between teammates. Keep them stable; if you need to change
one, flag it so the owners of neighbouring steps can adapt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TriggerType(str, Enum):
    PRESS_ARTICLE = "press_article"
    NEW_APPOINTMENT = "new_appointment"
    DORMANT_RELATIONSHIP = "dormant_relationship"
    FUNDING_ROUND = "funding_round"
    NEW_REGULATION = "new_regulation"
    EVENT = "event"


class Salience(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Relationship(str, Enum):
    COLD = "cold"
    WARM = "warm"
    DORMANT = "dormant"
    EXISTING_CLIENT = "existing_client"


# --- Step 01 raw output (file / JSONL format) -------------------------------- #
@dataclass
class RawSignal:
    """Raw signal produced by a scraper, written to signals_output.jsonl.

    Fields match the CLAUDE.md contract so the file is the handoff point between
    the scraping module (Step 1) and the scoring module (Step 2).
    """

    company: str
    sector: str           # canonical from targeting_matrix: "food" | "retail" | … | "unknown"
    geography: str        # "france" | "noram" | "north_east_asia" | … | "unknown"
    contact_function: str # "supply_chain" | "marketing" | … | "unknown"
    trigger: str          # short description of the signal
    source: str           # "MergerMarket" | "Les Echos" | …
    date: str             # ISO yyyy-mm-dd
    url: str = ""         # source URL (optional)


# --- Step 01 → 02 ----------------------------------------------------------- #
@dataclass
class Trigger:
    """A detected reason to reach out (from CRM / news / press)."""

    type: TriggerType
    summary: str
    source_url: str
    date: str  # ISO yyyy-mm-dd
    company: str
    sector: str           # "food" | "retail" | … | "unknown"
    geography: str        # "france" | "noram" | … | "unknown"
    contact_function: str # "marketing" | "it" | … | "unknown"
    salience: Salience = Salience.MEDIUM


# --- Step 02 → 03 ----------------------------------------------------------- #
@dataclass
class QualifiedTrigger:
    """A trigger that passed scoring and is worth acting on."""

    trigger: Trigger
    score: float  # 0..1
    reason: str  # why it's worth acting on


# --- Step 03 → 04 ----------------------------------------------------------- #
@dataclass
class ContactProfile:
    """The right person to contact and what we know about them."""

    full_name: str
    title: str
    company: str
    seniority: str  # C-level | VP | Director | Manager
    language: str  # "fr" | "en"
    relationship: Relationship
    linkedin_url: Optional[str] = None
    last_interaction: Optional[str] = None
    known_priorities: list[str] = field(default_factory=list)


@dataclass
class EmertonAssets:
    """Credentials / proof points / sender info used to draft (from the assets base)."""

    relevant_offer: str
    proof_points: list[str]
    sender_name: str
    sender_title: str
    sender_email: str
    credentials_url: Optional[str] = None


@dataclass
class StyleReference:
    """Past messages + tone used to calibrate the draft."""

    tone: str = "professional, direct, warm, no salesy jargon"
    past_messages: list[str] = field(default_factory=list)


@dataclass
class DraftRequest:
    """Everything step 04 needs to draft a message.

    ``contact`` carries the shared deal context (company, role, relationship, language).
    ``recipients`` lists the individual people on the deal: the email is one shared
    message greeting all of them, while LinkedIn is sent 1-to-1, one message per name.
    Defaults to the single contact when not set explicitly.
    """

    trigger: Trigger
    contact: ContactProfile
    assets: EmertonAssets
    style: StyleReference = field(default_factory=StyleReference)
    recipients: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.recipients:
            self.recipients = [self.contact.full_name]


# --- Step 04 → 05 ----------------------------------------------------------- #
@dataclass
class Email:
    subject: str
    body: str
    cta: str


@dataclass
class LinkedInDraft:
    """A 1-to-1 LinkedIn message for a single recipient."""

    recipient: str
    message: str


@dataclass
class OutreachDraft:
    """The drafted outputs plus review metadata.

    One shared ``email`` addressed to all recipients; ``linkedin`` holds one message
    per recipient (LinkedIn is strictly 1-to-1).
    """

    email: Email
    linkedin: list[LinkedInDraft]
    rationale: str
    confidence: str  # high | medium | low
    flags: list[str] = field(default_factory=list)


# --- Step 05 ---------------------------------------------------------------- #
@dataclass
class ReviewedOutreach:
    """Final decision after guardrails."""

    draft: OutreachDraft
    decision: str  # "auto_send" | "human_review" | "discard"
    notes: str = ""
