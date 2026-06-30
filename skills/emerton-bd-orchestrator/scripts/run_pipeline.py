#!/usr/bin/env python3
"""Orchestrator helper for the Emerton BD Watch pipeline.

Plans and reports an end-to-end run: detects which stages are available in this
checkout, parses any CRM/prospect Excel via the message-drafter's parser, and writes a
machine-readable run manifest. It does NOT draft messages itself — drafting is delegated
to the `emerton-message-drafter` skill (whose rules must not be re-implemented).

Self-contained (stdlib only). The Excel parse step shells out to the drafter's
parse_deals.py, which needs openpyxl.

Usage:
    python run_pipeline.py --input <file.xlsx>     # CRM path (Excel -> draft plan)
    python run_pipeline.py --discovery             # discovery path (watch -> ... -> draft)
    python run_pipeline.py --input f.xlsx --out run_manifest.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _find_repo_root(start: Path) -> Path | None:
    """Walk up looking for the bd-watch repo (has src/bd_watch or skills/)."""
    for p in [start, *start.parents]:
        if (p / "src" / "bd_watch").is_dir() or (p / "skills" / "emerton-message-drafter").is_dir():
            return p
    return None


def _locate_drafter_parser(script_dir: Path, repo_root: Path | None) -> Path | None:
    candidates = [
        script_dir.parent.parent / "emerton-message-drafter" / "scripts" / "parse_deals.py",
    ]
    if repo_root:
        candidates.append(repo_root / "skills" / "emerton-message-drafter" / "scripts" / "parse_deals.py")
    for c in candidates:
        if c.is_file():
            return c
    return None


def _detect_stages(repo_root: Path | None, drafter_parser: Path | None) -> dict:
    """Best-effort availability map for each pipeline stage in this checkout."""
    def has(*rel: str) -> bool:
        return bool(repo_root) and any((repo_root / r).exists() for r in rel)

    return {
        "01_watch": "available" if has("triggers_module", "src/bd_watch/scrapers") else "pending (branch feat/nominations-module)",
        "02_qualify": "available" if has("targeting_matrix.json") else "heuristic (matrix not present)",
        "03_contact": "available" if has("src/bd_watch/identify_contact") else "pending (branch feature/search_contact)",
        "04_draft": "available" if drafter_parser else "MISSING — install/locate emerton-message-drafter",
        "05_review": "available" if has("src/bd_watch/steps/step05_review.py") else "default gate (high & no-flags)",
        "code_pipeline": "available" if has("src/bd_watch/pipeline.py") else "n/a",
    }


def _parse_excel(parser: Path, xlsx: Path) -> dict:
    out = subprocess.run(
        [sys.executable, str(parser), str(xlsx)],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        return {"error": out.stderr.strip() or "parser failed", "input_type": "unknown", "rows": []}
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError as e:
        return {"error": f"could not parse JSON: {e}", "input_type": "unknown", "rows": []}


def _plan_from_parsed(parsed: dict) -> list[dict]:
    plan = []
    for r in parsed.get("rows", []):
        recips = r.get("recipients", [])
        plan.append({
            "company": r.get("company", ""),
            "recipients": recips,
            "relationship": r.get("relationship", ""),
            "deal_status": r.get("deal_status", ""),
            "draftable": bool(recips) and "archive_candidate" not in (r.get("triage") or []),
            "triage": r.get("triage", []),
        })
    return plan


def main() -> None:
    ap = argparse.ArgumentParser(description="Plan/report an Emerton BD Watch pipeline run.")
    ap.add_argument("--input", help="CRM/prospect/lost-deals Excel (.xlsx) for the CRM path.")
    ap.add_argument("--discovery", action="store_true", help="Discovery path (news watch -> ... -> draft).")
    ap.add_argument("--out", default="run_manifest.json", help="Where to write the run manifest JSON.")
    args = ap.parse_args()

    if not args.input and not args.discovery:
        ap.error("provide --input <file.xlsx> (CRM path) or --discovery (discovery path)")

    script_dir = Path(__file__).resolve().parent
    repo_root = _find_repo_root(script_dir)
    drafter_parser = _locate_drafter_parser(script_dir, repo_root)
    stages = _detect_stages(repo_root, drafter_parser)
    path = "discovery" if args.discovery else "crm"

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "path": path,
        "repo_root": str(repo_root) if repo_root else None,
        "stage_availability": stages,
        "drafter_parser": str(drafter_parser) if drafter_parser else None,
        "input": args.input,
        "input_type": None,
        "counts": {},
        "plan": [],
        "notes": [],
    }

    print(f"\n=== Emerton BD Watch — run plan ({path} path) ===")
    print(f"repo: {repo_root}")
    print("stage availability:")
    for k, v in stages.items():
        mark = "OK " if v.startswith("available") else "!! "
        print(f"  {mark}{k}: {v}")

    if args.input:
        xlsx = Path(args.input)
        if not xlsx.is_file():
            manifest["notes"].append(f"input file not found: {xlsx}")
            print(f"\n!! input not found: {xlsx}")
        elif not drafter_parser:
            manifest["notes"].append("drafter parser not found; cannot normalise the Excel")
            print("\n!! emerton-message-drafter parser not found — install the skill or run in the repo.")
        else:
            parsed = _parse_excel(drafter_parser, xlsx)
            manifest["input_type"] = parsed.get("input_type")
            manifest["counts"] = parsed.get("counts", {})
            manifest["plan"] = _plan_from_parsed(parsed)
            draftable = sum(1 for p in manifest["plan"] if p["draftable"])
            triaged = len(manifest["plan"]) - draftable
            print(f"\ninput_type: {manifest['input_type']}  counts: {manifest['counts']}")
            print(f"plan: {len(manifest['plan'])} rows -> {draftable} to draft, {triaged} to triage")
            print("\nNEXT: draft each draftable row with the emerton-message-drafter skill,")
            print("then apply the Review gate, then consolidate into outreach_run_review.md.")
    else:
        # step03 is "wired" only if it imports the identify_contact module rather than returning the
        # placeholder mock profile (the stub hard-codes "Marie Dupont").
        step03 = repo_root / "src/bd_watch/steps/step03_contact.py" if repo_root else None
        step03_text = step03.read_text(encoding="utf-8") if (step03 and step03.is_file()) else ""
        contact_wired = ("identify_contact" in step03_text and "Marie Dupont" not in step03_text)
        if stages["01_watch"].startswith("available") and stages["03_contact"].startswith("available"):
            manifest["notes"].append("discovery stages present — run: python -m bd_watch.pipeline")
            if not contact_wired:
                manifest["notes"].append("WARNING: step03_contact hook returns a MOCK profile (identify_contact module not wired) — mark contacts contact_unverified")
            print("\ndiscovery stages present. Run the code pipeline: python -m bd_watch.pipeline")
            if not contact_wired:
                print("!! step03 contact resolution is MOCKED — flag contacts as contact_unverified.")
        else:
            manifest["notes"].append(
                "discovery path partial: Watch and/or Contact not merged. Provide triggers/contacts "
                "manually or merge feat/nominations-module + feature/search_contact. Do not fabricate."
            )
            print("\n!! discovery path is partial (Watch/Contact not merged).")
            print("   Provide triggers/contacts manually, or merge the upstream branches.")
            print("   Then draft via emerton-message-drafter and apply the Review gate.")

    Path(args.out).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nmanifest written: {args.out}\n")


if __name__ == "__main__":
    main()
