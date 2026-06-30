"""
Pipeline : signal -> profil -> candidats Lusha+scraping -> classement LLM -> enrichissement top 3.
"""

from __future__ import annotations

from .models import SignalInput, IdentificationResult, Candidate
from .reasoning import deduce_target_profile, rank_candidates
from .lusha_client import LushaClient
from .web_fallback import web_fallback, scrape_people_from_url


def identify_contact(
    signal: SignalInput,
    our_angle: str,
    lusha: LushaClient,
    crm_lookup=None,
) -> IdentificationResult:
    sources: list[str] = []
    relationship_status = "new"

    # --- [0] CRM ------------------------------------------------------------ #
    if crm_lookup is not None:
        existing = crm_lookup(signal.target_organization)
        if existing:
            return IdentificationResult(
                signal_id=signal.signal_id,
                recommended_contact=existing,
                rationale="Contact déjà présent dans le CRM — relation existante à réactiver.",
                relationship_status="dormant",
                confidence=0.85,
                sources=["hubspot"],
            )

    # --- [1] LLM déduit le profil cible ------------------------------------- #
    profile = deduce_target_profile(signal, our_angle)

    # --- [2] Lusha : décideurs puis prospecting ------------------------------ #
    candidates: list[Candidate] = []
    try:
        candidates = lusha.find_decision_makers(signal.target_organization, limit=10)
        sources.append("lusha:decision-makers")
    except Exception as e:
        sources.append(f"lusha:decision-makers:error({type(e).__name__})")

    if len(candidates) < 2:
        try:
            more = lusha.prospect_contacts(signal.target_organization, profile, limit=25)
            seen = {c.lusha_id for c in candidates}
            candidates += [c for c in more if c.lusha_id not in seen]
            sources.append("lusha:prospecting")
        except Exception as e:
            sources.append(f"lusha:prospecting:error({type(e).__name__})")

    # --- [2b] Scraping du source_url ---------------------------------------- #
    # Nomination connue → candidat direct, pas besoin de scraper l'article.
    # Sinon → scraper en filtrant sur l'entreprise cible pour éviter les faux positifs.
    if signal.context.named_person and signal.context.source_url:
        from .web_fallback import find_linkedin_for_named_person
        named = signal.context.named_person
        linkedin = find_linkedin_for_named_person(named, signal.target_organization.name)
        if not linkedin:
            q = f"{named} {signal.target_organization.name}".replace(" ", "%20")
            linkedin = f"https://www.linkedin.com/search/results/people/?keywords={q}"
        named_candidate = Candidate(
            lusha_id=f"scraped_{named.lower().replace(' ', '_')}",
            name=named,
            title=signal.context.named_person_title or "",
            linkedin_url=linkedin,
        )
        if named.lower() not in {c.name.lower() for c in candidates}:
            candidates = [named_candidate] + candidates
        sources.append("source_url:named_person")
    elif signal.context.source_url:
        scraped = scrape_people_from_url(
            signal.context.source_url,
            company_name=signal.target_organization.name,
        )
        if scraped:
            seen_names = {c.name.lower() for c in candidates}
            added = [c for c in scraped if c.name.lower() not in seen_names]
            candidates = added + candidates
            sources.append(f"source_url:scraped({len(added)} persons)")

    # --- [2c] Fallback web si Lusha vide ------------------------------------ #
    if not candidates:
        web_candidate = web_fallback(signal, profile)
        if web_candidate:
            sources.append("web:linkedin_search")
            return IdentificationResult(
                signal_id=signal.signal_id,
                recommended_contact=web_candidate,
                rationale=(
                    "Contact trouvé via recherche web (Lusha sans résultat). "
                    + ("Personne nommée dans le signal." if signal.context.named_person
                       else "Rôle ciblé trouvé en ligne.")
                ),
                relationship_status=relationship_status,
                confidence=0.5 if signal.context.named_person else 0.3,
                target_profile=profile,
                sources=sources,
            )
        return IdentificationResult(
            signal_id=signal.signal_id, recommended_contact=None,
            rationale="Aucun contact trouvé (Lusha + recherche web).",
            relationship_status=relationship_status, confidence=0.0,
            target_profile=profile, sources=sources,
            error="no_candidates",
        )

    # --- [3] LLM classe les candidats --------------------------------------- #
    ranking = rank_candidates(signal, our_angle, profile, candidates)
    by_id = {c.lusha_id: c for c in candidates}
    best = by_id.get(ranking.get("recommended_id")) or candidates[0]
    alt_ids = ranking.get("alternative_ids", [])
    alts = [by_id[i] for i in alt_ids if i in by_id]

    # Complète alts jusqu'à 2 depuis le reste des candidats si besoin
    if len(alts) < 2:
        used = {best.lusha_id} | {a.lusha_id for a in alts}
        for c in candidates:
            if c.lusha_id not in used:
                alts.append(c)
            if len(alts) >= 2:
                break

    # --- [4] Enrichit les top 3 (winner + 2 alts) --------------------------- #
    def try_enrich(c: Candidate) -> Candidate:
        if c.lusha_id.startswith("scraped_") or c.lusha_id.startswith("web_"):
            return c  # pas d'ID Lusha réel → pas d'enrich
        try:
            return lusha.enrich_email(c)
        except Exception:
            return c

    best = try_enrich(best)
    alts = [try_enrich(a) for a in alts[:2]]
    sources.append("lusha:enrich(top3)")

    return IdentificationResult(
        signal_id=signal.signal_id,
        recommended_contact=best,
        rationale=ranking.get("rationale", ""),
        relationship_status=relationship_status,
        confidence=float(ranking.get("confidence", 0.5)),
        alternatives=alts,
        target_profile=profile,
        sources=sources,
    )
