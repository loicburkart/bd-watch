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

OUR_ANGLE = ("Banque d'affaires : nous vendons du conseil en M&A, "
             "financement et accompagnement de l'expansion internationale. "
             "Nous visons les décideurs financiers et la direction générale.")

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLES = os.path.join(os.path.dirname(HERE), "sample_signals.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--signal", required=True,
                    help="clé d'un signal de sample_signals.json")
    args = ap.parse_args()

    with open(SAMPLES, encoding="utf-8") as f:
        samples = json.load(f)
    if args.signal not in samples:
        print(f"Signal inconnu. Disponibles : {', '.join(samples)}")
        sys.exit(1)

    signal = SignalInput.from_dict(samples[args.signal])
    lusha = LushaClient()
    left = lusha.credits_left()
    if left is not None:
        print(f"[crédits Lusha restants: {left}]", file=sys.stderr)

    result = identify_contact(signal=signal, our_angle=OUR_ANGLE, lusha=lusha)

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
