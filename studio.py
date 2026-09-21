"""Inquiry Studio: dependency-free, offline production-planning core.

This is deliberately not an autonomous researcher or a media renderer yet.
It turns a versioned case packet into reproducible, clearly blocked production
briefs. Future model adapters must retain these provenance and release gates.
"""
import argparse
import hashlib
import json
from pathlib import Path

VERSION = "0.1.0"
FORMATS = {
    "short": ["question", "evidence", "limitation", "next test"],
    "podcast": ["human opening", "question", "hypothesis", "counterevidence", "test", "provisional conclusion"],
    "investigation": ["opening", "context", "competing explanations", "tests", "consequences"],
    "newsletter": ["question", "new evidence", "what changed", "next test"],
    "book": ["scene opportunity", "documented people", "evidence arc", "open questions"],
    "treatment": ["logline", "stakes", "access", "episode arc", "unresolved questions"],
}


def digest(value):
    """Stable content hashes make identical requests reusable, not new work."""
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def validate(packet):
    """Validate references before a writer sees them; never treat URLs as proof."""
    for field in ("id", "revision", "question", "canon", "sources", "claims", "hypotheses"):
        if field not in packet:
            raise ValueError("Missing field: " + field)
    if not isinstance(packet["revision"], int) or packet["revision"] < 1:
        raise ValueError("revision must be a positive integer")
    sources = packet["sources"]
    source_ids = [s["id"] for s in sources]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("Duplicate source IDs")
    claim_ids = [c["id"] for c in packet["claims"]]
    if len(claim_ids) != len(set(claim_ids)):
        raise ValueError("Duplicate claim IDs")
    for claim in packet["claims"]:
        if claim["type"] not in ("fact", "inference", "speculation"):
            raise ValueError("Unknown claim type")
        if not claim.get("source_ids") or not set(claim["source_ids"]) <= set(source_ids):
            raise ValueError("Claim has missing or unknown sources")
        if claim.get("status") not in ("pending", "verified", "disputed", "retracted"):
            raise ValueError("Unknown verification status")
    return packet


def compile_package(packet, format_name):
    """Produce an immutable planning artifact, not a pretend finished episode."""
    validate(packet)
    if format_name not in FORMATS:
        raise ValueError("Unknown format")
    usable = [c for c in packet["claims"] if c["status"] == "verified" and c["type"] != "speculation"]
    key = digest({"packet": packet, "format": format_name, "version": VERSION})
    return {
        "run_id": key, "engine_version": VERSION, "mode": "offline_preview",
        "case_id": packet["id"], "case_revision": packet["revision"],
        "input_sha256": digest(packet), "format": format_name,
        "status": "blocked", "publishable": False,
        "blockers": ["No final script or rendered media", "Human factual and rights review required"]
                    + ([] if usable else ["No verified claims available"]),
        "question": packet["question"], "canon": packet["canon"],
        "beats": [{"purpose": p, "content": None} for p in FORMATS[format_name]],
        "approved_claims": usable, "sources": packet["sources"],
        "hypotheses": packet["hypotheses"],
        "format_provenance": "Proposed editorial structure; not measured exemplar metadata",
        "cost": {"api_calls": 0, "generated_video_seconds": 0, "actual_usd": 0},
        "next_step": "Verify sources, then implement and connect paid production adapters",
    }


def save_package(package, output_root):
    """Write once. Content-derived filenames prevent user-controlled traversal.

    A completed artifact is a single JSON file: exclusive creation prevents
    concurrent callers from overwriting it. Repeated runs verify existing bytes.
    """
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / (package["run_id"] + ".json")
    content = json.dumps(package, indent=2, ensure_ascii=False) + "\n"
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(content)
    except FileExistsError:
        if path.read_text(encoding="utf-8") != content:
            raise ValueError("Existing artifact is incomplete or modified; refusing overwrite")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["validate", "preview"])
    parser.add_argument("--case", default="cases/mens-health.json")
    parser.add_argument("--format", choices=[*FORMATS, "all"], default="all")
    parser.add_argument("--output", default="outputs")
    args = parser.parse_args()
    try:
        packet = validate(json.loads(Path(args.case).read_text(encoding="utf-8")))
        if args.command == "validate":
            print("Case references valid; this does not verify scientific claims.")
            return
        names = FORMATS if args.format == "all" else [args.format]
        for name in names:
            path = save_package(compile_package(packet, name), args.output)
            print(f"{name}: BLOCKED PREVIEW — {path}")
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.exit(1, f"Cannot complete request: {error}\n")


if __name__ == "__main__":
    main()
