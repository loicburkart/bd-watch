"""
CLI — identify_contact pipeline.

  python -m identify_contact.cli --signal france_agentforce_expansion
  python -m identify_contact.cli --signal new_cdo_fleury_michon
"""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")

from .models import SignalInput
from .lusha_client import LushaClient
from .pipeline import identify_contact

_ANGLES_BY_TYPE = {
    "new_appointment": (
        "Nomination : une personne vient d'être nommée à un poste clé. "
        "Contacter directement la personne nommée ou son N+1 immédiat. "
        "Privilégier la fonction exacte du nommé (CDO → IT/digital, CFO → finance, etc.)."
    ),
    "m&a": (
        "Banque d'affaires : nous vendons du conseil en M&A, "
        "financement et accompagnement de l'expansion internationale. "
        "Nous visons les décideurs financiers et la direction générale."
    ),
    "expansion": (
        "Expansion : l'entreprise ouvre un nouveau marché ou pays. "
        "Viser le directeur pays, le COO ou le responsable du développement international."
    ),
    "job_opening": (
        "Recrutement stratégique : un poste senior est ouvert, signe d'un projet. "
        "Viser le DRH ou le manager direct du poste ouvert."
    ),
    "press_article": (
        "Signal presse : une actualité notable concerne l'entreprise. "
        "Viser le décideur le plus directement lié au sujet de l'article."
    ),
}

_DEFAULT_ANGLE = (
    "Signal générique : identifier le décideur le plus pertinent "
    "en lien direct avec le sujet du signal, quel que soit son département."
)

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLES = os.path.join(os.path.dirname(HERE), "sample_signals.json")


def _resolve_angle(signal: "SignalInput", override: str | None) -> str:
    if override:
        return override
    return _ANGLES_BY_TYPE.get(signal.type, _DEFAULT_ANGLE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--signal", required=True,
                    help="clé d'un signal de sample_signals.json")
    ap.add_argument("--angle", default=None,
                    help="angle de prospection (optionnel, sinon déduit du type de signal)")
    args = ap.parse_args()

    with open(SAMPLES, encoding="utf-8") as f:
        samples = json.load(f)
    if args.signal not in samples:
        print(f"Signal inconnu. Disponibles : {', '.join(samples)}")
        sys.exit(1)

    signal = SignalInput.from_dict(samples[args.signal])
    our_angle = _resolve_angle(signal, args.angle)
    print(f"[angle] {our_angle}", file=sys.stderr)

    lusha = LushaClient()
    left = lusha.credits_left()
    if left is not None:
        print(f"[crédits Lusha restants: {left}]", file=sys.stderr)

    result = identify_contact(signal=signal, our_angle=our_angle, lusha=lusha)

    contacts = []
    for c in ([result.recommended_contact] if result.recommended_contact else []) + result.alternatives:
        contacts.append({
            "name": c.name,
            "title": c.title or None,
            "company": signal.target_organization.name,
            "email": c.email or None,
            "linkedin": c.linkedin_url or None,
            "context": signal.context.summary,
            "rationale": result.rationale,
        })

    out_path = Path(__file__).parent.parent / f"result_{args.signal}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(contacts, f, indent=2, ensure_ascii=False)
    print(f"Résultat écrit dans : {out_path}", file=sys.stderr)
    print(json.dumps(contacts, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
