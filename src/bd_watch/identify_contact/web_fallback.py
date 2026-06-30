"""
Fallback web search quand Lusha ne trouve pas de contacts.

Stratégie :
  1. Si named_person → chercher son profil LinkedIn par nom + entreprise (DDG)
  2. Sinon → chercher qui occupe le rôle cible dans l'entreprise (DDG),
             puis récupérer son URL LinkedIn

On utilise DuckDuckGo (pas de clé API, pas de quota strict).
"""

from __future__ import annotations

import re
import time
from typing import Optional

from .models import Candidate, SignalInput, TargetProfile, TargetOrganization


# --------------------------------------------------------------------------- #
# Recherche DuckDuckGo
# --------------------------------------------------------------------------- #
def _ddg_search(query: str, max_results: int = 8) -> list[dict]:
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results))
    except Exception:
        return []


def _extract_linkedin_url(results: list[dict]) -> Optional[str]:
    """Extrait la première URL linkedin.com/in/... trouvée dans les résultats."""
    for r in results:
        for field in ("href", "url", "link"):
            url = r.get(field, "")
            match = re.search(r'https?://(?:www\.)?linkedin\.com/in/([\w\-]+)', url)
            if match:
                return f"https://www.linkedin.com/in/{match.group(1)}"
    # Cherche aussi dans les snippets (parfois l'URL y est en texte)
    for r in results:
        body = r.get("body", "") + r.get("snippet", "")
        match = re.search(r'linkedin\.com/in/([\w\-]+)', body)
        if match:
            return f"https://www.linkedin.com/in/{match.group(1)}"
    return None


# --------------------------------------------------------------------------- #
# Cas 1 : personne nommée → trouver son LinkedIn
# --------------------------------------------------------------------------- #
def find_linkedin_for_named_person(name: str, company: str) -> Optional[str]:
    """Cherche le profil LinkedIn d'une personne nommée via DuckDuckGo."""
    # Tentative 1 : recherche ciblée site:linkedin.com
    results = _ddg_search(f'"{name}" "{company}" site:linkedin.com/in', max_results=5)
    url = _extract_linkedin_url(results)
    if url:
        return url

    time.sleep(1)  # évite le rate-limit DDG

    # Tentative 2 : recherche plus large
    results = _ddg_search(f'{name} {company} linkedin profil', max_results=8)
    return _extract_linkedin_url(results)


# --------------------------------------------------------------------------- #
# Cas 2 : pas de personne nommée → chercher par rôle
# --------------------------------------------------------------------------- #
def find_person_by_role(profile: TargetProfile, org: TargetOrganization) -> Optional[tuple[str, str]]:
    """
    Cherche qui occupe un rôle donné dans une entreprise.
    Retourne (nom, linkedin_url) ou None.
    """
    # Construit une requête à partir du profil déduit par le LLM
    role_terms = (profile.keywords[:2] if profile.keywords
                  else [profile.function])
    role_query = " ".join(role_terms)
    company = org.name

    # Tentative 1 : recherche directe LinkedIn
    results = _ddg_search(
        f'{role_query} {company} site:linkedin.com/in', max_results=8
    )
    url = _extract_linkedin_url(results)
    if url:
        name = _name_from_linkedin_slug(url)
        return name, url

    time.sleep(1)

    # Tentative 2 : recherche plus large puis extraction LinkedIn
    results = _ddg_search(f'{role_query} {company} linkedin', max_results=10)
    url = _extract_linkedin_url(results)
    if url:
        name = _name_from_linkedin_slug(url)
        return name, url

    return None


def _name_from_linkedin_slug(url: str) -> str:
    """Transforme linkedin.com/in/sebastien-gautier en 'Sebastien Gautier'."""
    slug = url.rstrip("/").split("/")[-1]
    # Supprime les suffixes numériques (ex: john-doe-1234b)
    slug = re.sub(r'-\w{4,}$', '', slug)
    return " ".join(part.capitalize() for part in slug.split("-"))


# --------------------------------------------------------------------------- #
# Interface principale du fallback
# --------------------------------------------------------------------------- #
def web_fallback(signal: SignalInput, profile: TargetProfile) -> Optional[Candidate]:
    """
    Retourne un Candidate via recherche web quand Lusha est vide.
    Priorité : personne nommée > recherche par rôle.
    """
    named = signal.context.named_person

    if named:
        # Cas 1 : on cherche directement la personne nommée
        linkedin_url = find_linkedin_for_named_person(named, signal.target_organization.name)
        if not linkedin_url:
            # Fallback : URL de recherche LinkedIn cliquable
            q = f"{named} {signal.target_organization.name}".replace(" ", "%20")
            linkedin_url = f"https://www.linkedin.com/search/results/people/?keywords={q}"

        return Candidate(
            lusha_id=f"web_named_{named.lower().replace(' ', '_')}",
            name=named,
            title=signal.context.named_person_title or "",
            location=signal.target_organization.country or "",
            linkedin_url=linkedin_url,
        )

    else:
        # Cas 2 : on cherche par rôle
        result = find_person_by_role(profile, signal.target_organization)
        if result:
            name, linkedin_url = result
            return Candidate(
                lusha_id=f"web_role_{name.lower().replace(' ', '_')}",
                name=name,
                title=" / ".join(profile.keywords[:2]) if profile.keywords else profile.function,
                location=signal.target_organization.country or "",
                linkedin_url=linkedin_url,
            )

    return None


# --------------------------------------------------------------------------- #
# Scraping d'un article source_url → liste de Candidates
# --------------------------------------------------------------------------- #
def scrape_people_from_url(url: Optional[str], company_name: str = "") -> list[Candidate]:
    """
    Fetche l'URL du signal, extrait le texte, demande au LLM de lister
    uniquement les personnes *en poste actuel* dans l'entreprise cible,
    puis cherche leur LinkedIn.
    Retourne une liste de Candidate (lusha_id préfixé 'scraped_').
    """
    if not url:
        return []
    try:
        import requests as _req
        from bs4 import BeautifulSoup
        r = _req.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.text, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)[:4000]
    except Exception:
        return []

    company_filter = (
        f"Ne garde que les personnes qui travaillent actuellement chez {company_name}. "
        if company_name else ""
    )

    try:
        import os
        import json as _json
        from .llm import get_client
        client = get_client()
        resp = client.chat.completions.create(
            model=os.environ["DATABRICKS_ENDPOINT"],
            messages=[
                {"role": "system", "content": (
                    "Tu extrais les personnes nommées d'un article. "
                    f"{company_filter}"
                    "Exclure : journalistes, auteurs de l'article, historiques/fondateurs, "
                    "personnes d'autres entreprises. "
                    "Renvoie UNIQUEMENT un JSON valide : "
                    "{\"people\": [{\"name\": \"...\", \"title\": \"...\"}]}"
                )},
                {"role": "user", "content": f"Article:\n{text}"},
            ],
            max_tokens=512,
        )
        raw = resp.choices[0].message.content or ""
        start = raw.find("{")
        end = raw.rfind("}") + 1
        data = _json.loads(raw[start:end])
        people = data.get("people", [])
    except Exception:
        return []

    candidates = []
    for p in people[:5]:
        name = p.get("name", "").strip()
        title = p.get("title", "").strip()
        if not name:
            continue
        linkedin = find_linkedin_for_named_person(name, company_name)
        if not linkedin:
            q = f"{name} {company_name}".replace(" ", "%20")
            linkedin = f"https://www.linkedin.com/search/results/people/?keywords={q}"
        candidates.append(Candidate(
            lusha_id=f"scraped_{name.lower().replace(' ', '_')}",
            name=name,
            title=title,
            linkedin_url=linkedin,
        ))
    return candidates
