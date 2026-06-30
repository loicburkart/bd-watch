"""Loaders for Emerton assets (credentials, proof points) and style reference.

These come from the assets base (other hackathon team). For now they load from
``data/samples/``; swap in the real source later.
"""

from __future__ import annotations

import json
from pathlib import Path

from .schemas import EmertonAssets, StyleReference

_SAMPLES = Path(__file__).resolve().parents[2] / "data" / "samples"


def load_emerton_assets() -> EmertonAssets:
    data = json.loads((_SAMPLES / "emerton_assets.json").read_text())
    s = data["sender"]
    return EmertonAssets(
        relevant_offer=data["relevant_offer"],
        proof_points=data["proof_points"],
        sender_name=s["name"],
        sender_title=s["title"],
        sender_email=s["email"],
        credentials_url=data.get("credentials_url"),
    )


def load_style_reference() -> StyleReference:
    data = json.loads((_SAMPLES / "style_reference.json").read_text())
    return StyleReference(
        tone=data.get("tone", "professional, direct, warm, no salesy jargon"),
        past_messages=data.get("past_messages", []),
    )
