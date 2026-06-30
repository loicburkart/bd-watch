"""
Raisonnement LLM — deux appels via Databricks (compatible OpenAI) :
  [1] deduce_target_profile  -> qui chercher (fonction / séniorité / géo)
  [3] rank_candidates        -> qui contacter + pourquoi + confiance
"""

from __future__ import annotations

import json
import os

from .models import SignalInput, TargetProfile, Candidate


def _call_llm(system: str, user: str, max_tokens: int = 1024) -> str:
    from .llm import get_client
    client = get_client()
    resp = client.chat.completions.create(
        model=os.environ["DATABRICKS_ENDPOINT"],
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content or ""


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{"):]
    start, depth = text.find("{"), 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    raise ValueError(f"Pas de JSON valide dans: {text[:200]}")


# --------------------------------------------------------------------------- #
# [1] Déduire le profil cible
# --------------------------------------------------------------------------- #
_PROFILE_SYSTEM = """Tu aides une équipe commerciale à identifier QUI contacter \
dans une entreprise cible, à partir d'un signal (actualité, nomination, etc.) \
et de l'angle de prospection de l'équipe.

Renvoie UNIQUEMENT un objet JSON, sans texte autour, avec ce schéma :
{
  "function": "<fonction principale à viser, ex: finance>",
  "seniority": ["c_level" | "vp" | "director" | "manager"],
  "departments": ["finance" | "sales" | "general_management" | "strategy" | "hr" | "marketing" | "it" | "operations" | "engineering" | ...],
  "location_country": "<code pays ISO si le signal en désigne un, sinon null>",
  "keywords": ["mots-clés de titre de poste pertinents"],
  "reasoning": "<1-2 phrases : pourquoi ce profil pour CE signal et CET angle>"
}
Raisonne sur l'intention derrière le signal, pas seulement sur les mots."""


def deduce_target_profile(signal: SignalInput, our_angle: str) -> TargetProfile:
    user = f"""SIGNAL
- type : {signal.type}
- entreprise : {signal.target_organization.name}
- pays entreprise : {signal.target_organization.country}
- résumé : {signal.context.summary}
- sujet : {signal.context.topic}
- personne nommée : {signal.context.named_person or "aucune"}

NOTRE ANGLE DE PROSPECTION : {our_angle}

Quel profil viser ?"""
    data = _extract_json(_call_llm(_PROFILE_SYSTEM, user))
    return TargetProfile(
        function=data.get("function", ""),
        seniority=data.get("seniority", []),
        departments=data.get("departments", []),
        keywords=data.get("keywords", []),
        location_country=data.get("location_country"),
        reasoning=data.get("reasoning", ""),
    )


# --------------------------------------------------------------------------- #
# [3] Classer les candidats
# --------------------------------------------------------------------------- #
_RANK_SYSTEM = """Tu classes des contacts d'une entreprise pour décider lequel \
contacter suite à un signal commercial précis.

Renvoie UNIQUEMENT un objet JSON :
{
  "recommended_id": "<lusha_id du meilleur contact>",
  "rationale": "<pourquoi cette personne, en lien explicite avec le signal>",
  "confidence": <nombre 0.0-1.0>,
  "alternative_ids": ["<lusha_id>", ...]
}"""


def rank_candidates(signal: SignalInput, our_angle: str, profile: TargetProfile,
                    candidates: list[Candidate]) -> dict:
    if not candidates:
        return {"recommended_id": None, "rationale": "Aucun candidat trouvé.",
                "confidence": 0.0, "alternative_ids": []}

    listing = "\n".join(
        f"- id={c.lusha_id} | {c.name} | {c.title} | séniorité={c.seniority} "
        f"| dépt={c.department} | lieu={c.location}"
        for c in candidates
    )
    user = f"""SIGNAL : {signal.context.summary} (type: {signal.type})
NOTRE ANGLE : {our_angle}
PROFIL VISÉ : {profile.function} / {profile.seniority} / {profile.reasoning}

CANDIDATS :
{listing}

Lequel contacter ?"""
    return _extract_json(_call_llm(_RANK_SYSTEM, user))
