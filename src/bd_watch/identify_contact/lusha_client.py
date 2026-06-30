"""
Client Lusha V3 — découverte + enrichissement des contacts.

Deux implémentations interchangeables (même interface) :
  - LushaClient      : appelle la vraie API V3 (consomme des crédits).
  - MockLushaClient  : renvoie des données en dur, ZÉRO crédit, ZÉRO clé.
"""

from __future__ import annotations

import os
from typing import Optional

import requests

from .models import Candidate, TargetProfile, TargetOrganization

LUSHA_BASE = "https://api.lusha.com"

# Lusha V3 numeric seniority IDs (GET /v3/contacts/prospecting/filters/seniority)
SENIORITY_MAP = {
    "c_level": 9, "c-suite": 9, "c_suite": 9,
    "vp": 8, "vice_president": 8,
    "director": 6,
    "manager": 5,
    "senior": 4,
    "individual": 3, "entry": 3,
    "intern": 2,
    "other": 1,
}

# Tous les séniorités pertinents pour un signal commercial (large par défaut)
DEFAULT_SENIORITY_IDS = [9, 8, 6, 5]  # c-suite, VP, director, manager

# Lusha V3 department strings (GET /v3/contacts/prospecting/filters/departments)
DEPARTMENT_MAP = {
    "finance": "Finance",
    "general_management": "General Management",
    "strategy": "Business Development",
    "business_development": "Business Development",
    "sales": "Sales",
    "commercial": "Sales",
    "hr": "Human Resources",
    "human_resources": "Human Resources",
    "marketing": "Marketing",
    "engineering": "Engineering & Technical",
    "technical": "Engineering & Technical",
    "it": "Information Technology",
    "information_technology": "Information Technology",
    "product": "Product",
    "legal": "Legal",
    "operations": "Operations",
    "supply_chain": "Operations",
    "research": "Research & Analytics",
    "analytics": "Research & Analytics",
    "customer_service": "Customer Service",
    "consulting": "Consulting",
    "healthcare": "Health Care & Medical",
}

# Tous les départements Lusha (fallback quand aucun profil n'est déduit)
ALL_DEPARTMENTS = [
    "Finance", "General Management", "Business Development", "Sales",
    "Engineering & Technical", "Information Technology", "Operations",
    "Marketing", "Product", "Research & Analytics", "Consulting", "Legal",
]


class LushaClient:
    """Vraie API Lusha V3."""

    def __init__(self, api_key: Optional[str] = None, timeout: int = 30):
        self.api_key = api_key or os.environ.get("LUSHA_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "Pas de clé Lusha. Mets LUSHA_API_KEY dans l'environnement, "
                "ou utilise MockLushaClient pour développer sans crédit."
            )
        self.timeout = timeout
        self._headers = {"api_key": self.api_key, "Content-Type": "application/json"}

    # --- garde-fou crédits ------------------------------------------------- #
    def credits_left(self) -> Optional[int]:
        try:
            r = requests.get(f"{LUSHA_BASE}/v3/account/usage",
                             headers=self._headers, timeout=self.timeout)
            r.raise_for_status()
            data = r.json()
            if "credits" in data and "remaining" in data["credits"]:
                return data["credits"]["remaining"]
            for k in ("creditsLeft", "remaining", "credits_remaining"):
                if k in data:
                    return data[k]
            return None
        except Exception:
            return None

    # --- recherche de l'entreprise dans Lusha ----------------------------- #
    def _find_lusha_company(self, org: TargetOrganization) -> dict:
        """Résout le nom/domaine en fiche Lusha (id + nom officiel + domaine)."""
        item: dict = {}
        if org.domain:
            item["domain"] = org.domain
        elif org.name:
            item["name"] = org.name
        if not item:
            return {}
        try:
            r = requests.post(f"{LUSHA_BASE}/v3/companies/search",
                              headers=self._headers, json={"companies": [item]},
                              timeout=self.timeout)
            if not r.ok:
                return {}
            results = r.json().get("results", [])
            if results:
                return results[0]
        except Exception:
            pass
        return {}

    # --- [2a] découverte : décideurs d'une entreprise ---------------------- #
    def find_decision_makers(self, org: TargetOrganization, limit: int = 10) -> list[Candidate]:
        """Voie principale : entreprise -> décideurs pertinents (aperçus gratuits)."""
        lusha_co = self._find_lusha_company(org)
        company_item: dict = {}
        if lusha_co.get("id"):
            company_item["id"] = str(lusha_co["id"])
        elif org.domain:
            company_item["domain"] = org.domain
        else:
            return []
        body = {"companies": [company_item]}
        r = requests.post(f"{LUSHA_BASE}/v3/contacts/decision-makers",
                          headers=self._headers, json=body, timeout=self.timeout)
        r.raise_for_status()
        return self._parse_previews(r.json())

    # --- [2b] prospecting large par filtres -------------------------------- #
    def prospect_contacts(self, org: TargetOrganization, profile: TargetProfile,
                          limit: int = 25) -> list[Candidate]:
        """Recherche filtrée — séniorité/département larges + filtre entreprise par ID."""
        # Séniorité : utilise le profil ou prend tous les niveaux pertinents
        if profile.seniority:
            seniority_ids = [SENIORITY_MAP[s] for s in profile.seniority if s in SENIORITY_MAP]
        else:
            seniority_ids = DEFAULT_SENIORITY_IDS
        if not seniority_ids:
            seniority_ids = DEFAULT_SENIORITY_IDS

        # Départements : utilise le profil ou prend tout
        if profile.departments:
            depts = [DEPARTMENT_MAP[d] for d in profile.departments if d in DEPARTMENT_MAP]
        else:
            depts = ALL_DEPARTMENTS
        if not depts:
            depts = ALL_DEPARTMENTS

        contact_include: dict = {"seniority": seniority_ids, "departments": depts}

        # Filtre entreprise : nom officiel Lusha (depuis company search) > nom brut
        company_include: dict = {}
        lusha_co = self._find_lusha_company(org)
        official_name = lusha_co.get("name") or org.name
        if official_name:
            company_include["names"] = [official_name]

        body = {
            "pagination": {"page": 1, "size": min(limit, 50)},
            "filters": {
                "contacts": {"include": contact_include},
                "companies": {"include": company_include} if company_include else {},
            },
        }
        r = requests.post(f"{LUSHA_BASE}/v3/contacts/prospecting",
                          headers=self._headers, json=body, timeout=self.timeout)
        if not r.ok:
            raise RuntimeError(f"Lusha prospecting {r.status_code}: {r.text[:400]}")
        return self._parse_previews(r.json())

    # --- [4] enrichissement : révèle l'email du gagnant (1 crédit) --------- #
    MIN_CREDITS_BEFORE_ENRICH = 2

    def enrich_email(self, candidate: Candidate) -> Candidate:
        """Révèle UNIQUEMENT l'email (1 crédit). Pas de téléphone."""
        left = self.credits_left()
        if left is not None and left < self.MIN_CREDITS_BEFORE_ENRICH:
            raise RuntimeError(
                f"Crédits Lusha insuffisants ({left} restants) — enrichissement annulé."
            )
        # V3 enrich format: {"ids": ["v1.xxx"]} — coûte ~6 crédits
        body = {"ids": [candidate.lusha_id]}
        r = requests.post(f"{LUSHA_BASE}/v3/contacts/enrich",
                          headers=self._headers, json=body, timeout=self.timeout)
        if not r.ok:
            raise RuntimeError(f"Lusha enrich {r.status_code}: {r.text[:300]}")
        results = r.json().get("results") or []
        if results:
            c = results[0]
            # Email
            emails = c.get("emails") or []
            if emails:
                candidate.email = emails[0].get("email") if isinstance(emails[0], dict) else emails[0]
            # Title / department (V3 : imbriqués dans jobTitle)
            job = c.get("jobTitle") or {}
            if not candidate.title:
                candidate.title = job.get("title") or self._str_field(c.get("title"))
            if not candidate.department:
                depts = job.get("departments") or []
                candidate.department = depts[0] if depts else ""
            if not candidate.seniority:
                candidate.seniority = job.get("seniority") or ""
            # LinkedIn
            if not candidate.linkedin_url:
                candidate.linkedin_url = (c.get("socialLinks") or {}).get("linkedin")
        return candidate

    # --- parsing tolérant des réponses V3 ---------------------------------- #
    @staticmethod
    def _str_field(val) -> str:
        if not val:
            return ""
        if isinstance(val, str):
            return val
        if isinstance(val, dict):
            return val.get("name") or val.get("value") or val.get("label") or ""
        return str(val)

    @staticmethod
    def _str_location(val) -> str:
        if not val:
            return ""
        if isinstance(val, str):
            return val
        if isinstance(val, dict):
            parts = [val.get("city"), val.get("state"), val.get("country")]
            return ", ".join(p for p in parts if p)
        return str(val)

    @classmethod
    def _parse_previews(cls, data: dict) -> list[Candidate]:
        raw: list = []
        if "results" in data and isinstance(data["results"], list):
            for entry in data["results"]:
                if "decisionMakers" in entry:
                    raw.extend(entry["decisionMakers"])
                else:
                    raw.append(entry)
        elif "data" in data and isinstance(data["data"], list):
            for entry in data["data"]:
                if "decisionMakers" in entry:
                    raw.extend(entry["decisionMakers"])
                else:
                    raw.append(entry)
        elif "contacts" in data:
            raw = data["contacts"]

        out: list[Candidate] = []
        for c in raw:
            name = (c.get("name")
                    or f"{c.get('firstName', '')} {c.get('lastName', '')}".strip()
                    or f"{c.get('first_name', '')} {c.get('last_name', '')}".strip())
            out.append(Candidate(
                lusha_id=str(c.get("id") or c.get("contactId") or ""),
                name=name,
                title=cls._str_field(c.get("title") or c.get("jobTitle") or c.get("job_title")),
                seniority=cls._str_field(c.get("seniority")),
                department=cls._str_field(c.get("department")),
                location=cls._str_location(c.get("location") or c.get("country")),
                linkedin_url=c.get("linkedinUrl") or c.get("linkedin_url"),
            ))
        return [c for c in out if c.lusha_id and c.name]


# --------------------------------------------------------------------------- #
# MOCK : pour développer/démo sans clé ni crédit.
# --------------------------------------------------------------------------- #
class MockLushaClient:
    """Fausse data, même interface. Contient des distracteurs pour prouver le tri."""

    _EMPLOYEES = [
        Candidate("dm_001", "Klaus Müller", "Country Manager Germany / Geschäftsführer",
                  seniority="c_level", department="general_management", location="Berlin, DE",
                  linkedin_url="https://linkedin.com/in/klausmueller"),
        Candidate("dm_002", "Sophie Bernard", "Directrice Administrative et Financière (CFO)",
                  seniority="c_level", department="finance", location="Paris, FR",
                  linkedin_url="https://linkedin.com/in/sophiebernard"),
        Candidate("dm_003", "Tom Weber", "Sales Director DACH",
                  seniority="director", department="sales", location="Munich, DE",
                  linkedin_url="https://linkedin.com/in/tomweber"),
        Candidate("dm_004", "Marie Dubois", "Chief Strategy Officer",
                  seniority="c_level", department="strategy", location="Paris, FR",
                  linkedin_url="https://linkedin.com/in/mariedubois"),
        Candidate("dm_005", "Lucas Petit", "Product Manager",
                  seniority="manager", department="product", location="Lyon, FR"),
        Candidate("dm_006", "Anna Schmidt", "HR Business Partner",
                  seniority="manager", department="hr", location="Berlin, DE"),
        Candidate("dm_007", "Hugo Martin", "Software Engineer",
                  seniority="individual", department="engineering", location="Nantes, FR"),
        Candidate("dm_008", "Emma Roux", "Marketing Intern",
                  seniority="individual", department="marketing", location="Paris, FR"),
    ]

    def credits_left(self) -> Optional[int]:
        return 999_999

    def find_decision_makers(self, org: TargetOrganization, limit: int = 10) -> list[Candidate]:
        import copy
        return [copy.deepcopy(c) for c in self._EMPLOYEES[:limit]]

    def prospect_contacts(self, org: TargetOrganization, profile: TargetProfile,
                          limit: int = 25) -> list[Candidate]:
        import copy
        return [copy.deepcopy(c) for c in self._EMPLOYEES[:limit]]

    def enrich_email(self, candidate: Candidate) -> Candidate:
        first = candidate.name.split()[0].lower().replace("ü", "u").replace("é", "e")
        candidate.email = f"{first}@acme.com"
        return candidate
