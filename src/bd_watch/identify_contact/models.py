"""
Modèles de données = le CONTRAT entre les briques du hackathon.

- SignalInput  : ce que le groupe "captation des signaux" nous passe.
- TargetProfile: ce que Claude déduit (fonction/séniorité à viser).
- Candidate    : un contact possible (aperçu Lusha, non enrichi).
- IdentificationResult : ce qu'on passe à la brique "rédaction du message".

Tout passe en JSON entre les groupes, donc chaque dataclass a un .to_dict() /
from_dict() pour sérialiser proprement.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


# --------------------------------------------------------------------------- #
# INPUT : ce que la captation nous envoie
# --------------------------------------------------------------------------- #
@dataclass
class TargetOrganization:
    name: str
    domain: Optional[str] = None          # ex: "acme.com" -> clé pour Lusha
    linkedin_url: Optional[str] = None
    country: Optional[str] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class SignalContext:
    summary: str                          # résumé en clair du signal
    topic: Optional[str] = None           # ex: "expansion", "m&a", "rh"
    named_person: Optional[str] = None    # souvent absent
    named_person_title: Optional[str] = None  # titre du nommé si connu
    source_url: Optional[str] = None
    date: Optional[str] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class SignalInput:
    signal_id: str
    type: str                             # press_article | new_appointment | dormant_relationship | job_opening | m&a ...
    target_organization: TargetOrganization
    context: SignalContext

    @staticmethod
    def from_dict(d: dict) -> "SignalInput":
        known_context = {"summary", "topic", "named_person", "named_person_title", "source_url", "date"}
        ctx = {k: v for k, v in d["context"].items() if k in known_context}
        known_org = {"name", "domain", "linkedin_url", "country"}
        org = {k: v for k, v in d["target_organization"].items() if k in known_org}
        return SignalInput(
            signal_id=d["signal_id"],
            type=d.get("type", "unknown"),
            target_organization=TargetOrganization(**org),
            context=SignalContext(**ctx),
        )

    def to_dict(self) -> dict:
        return {
            "signal_id": self.signal_id,
            "type": self.type,
            "target_organization": self.target_organization.to_dict(),
            "context": self.context.to_dict(),
        }


# --------------------------------------------------------------------------- #
# RAISONNEMENT : le profil cible déduit par Claude
# --------------------------------------------------------------------------- #
@dataclass
class TargetProfile:
    """Le 'qui chercher', déduit du signal + de notre angle de prospection."""
    function: str                         # ex: "finance", "general management"
    seniority: list[str] = field(default_factory=list)   # ex: ["c_level", "vp"]
    departments: list[str] = field(default_factory=list) # mappé vers filtres Lusha
    keywords: list[str] = field(default_factory=list)    # ex: ["Germany", "DACH", "country manager"]
    location_country: Optional[str] = None
    reasoning: str = ""                   # pourquoi ce profil (utile pour debug + démo)

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
# CANDIDATS : aperçus renvoyés par Lusha (non enrichis)
# --------------------------------------------------------------------------- #
@dataclass
class Candidate:
    lusha_id: str
    name: str
    title: str
    seniority: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    # email rempli seulement après enrichissement Lusha (1 crédit)
    email: Optional[str] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


# --------------------------------------------------------------------------- #
# OUTPUT : ce qu'on passe à la brique "rédaction"
# --------------------------------------------------------------------------- #
@dataclass
class IdentificationResult:
    signal_id: str
    recommended_contact: Optional[Candidate]
    rationale: str
    relationship_status: str              # new | existing_active | dormant
    confidence: float                     # 0.0 - 1.0
    alternatives: list[Candidate] = field(default_factory=list)
    target_profile: Optional[TargetProfile] = None
    sources: list[str] = field(default_factory=list)
    error: Optional[str] = None           # rempli si on n'a trouvé personne

    def to_dict(self) -> dict:
        return {
            "signal_id": self.signal_id,
            "recommended_contact": self.recommended_contact.to_dict() if self.recommended_contact else None,
            "rationale": self.rationale,
            "relationship_status": self.relationship_status,
            "confidence": round(self.confidence, 2),
            "alternatives": [c.to_dict() for c in self.alternatives],
            "target_profile": self.target_profile.to_dict() if self.target_profile else None,
            "sources": self.sources,
            "error": self.error,
        }
