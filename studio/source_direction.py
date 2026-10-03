"""Keep the people and provenance behind evidence audible in a short script."""
from __future__ import annotations

import re


def verified_sources(research):
    """Only sources already checked by Research can become spoken source beats."""
    result = {}
    for item in research.get("strongest_evidence", []):
        if not isinstance(item, dict):
            continue
        key, url = item.get("source_id"), item.get("url")
        if key and isinstance(url, str) and url.startswith("https://"):
            result[key] = {
                "source_id": key, "url": url, "author": item.get("author"),
                "year": item.get("year"), "finding_supported": item.get("finding_supported"),
                "source_type": item.get("source_type"), "interest_or_limit": item.get("interest_or_limit"),
            }
    return result


def script_issues(script, research, target_seconds):
    """Return repair feedback before a script can be locked or sent to speech."""
    sources = verified_sources(research)
    claims = {c.get("claim_id") or c.get("id"): c for c in research.get("claims", []) if isinstance(c, dict)}
    usable_urls = {x["url"] for x in sources.values()}
    required = min(2 if target_seconds >= 45 else 1, len(usable_urls))
    used = set()
    issues = []
    sentences = script.get("script") or []
    if not sentences:
        return ["No spoken sentences were returned"]
    if required == 0:
        return ["Research found no verified source URLs; research again before writing"]
    for index, sentence in enumerate(sentences, 1):
        line = str(sentence.get("text") or "")
        if len(re.findall(r"\b\d+(?:\.\d+)?\b", line)) > 3:
            issues.append(f"Sentence {index}: put the scoreboard in a visual; speak at most three numbers")
        source_id = sentence.get("spoken_source_id")
        if not source_id:
            continue
        source = sources.get(source_id)
        if not source:
            issues.append(f"Sentence {index}: spoken_source_id must identify a verified Research source")
            continue
        attribution = str(sentence.get("spoken_attribution") or "").strip()
        if not attribution or attribution.casefold() not in line.casefold():
            issues.append(f"Sentence {index}: the named source must actually be spoken in text")
        if not sentence.get("claim_ids"):
            issues.append(f"Sentence {index}: a source beat needs a supported claim_id")
        claim_sources = set()
        for claim_id in sentence.get("claim_ids") or []:
            claim = claims.get(claim_id) or {}
            for citation in claim.get("citations", []):
                if isinstance(citation, str):
                    claim_sources.add(sources.get(citation, {}).get("url", citation))
                elif isinstance(citation, dict):
                    claim_sources.add(citation.get("url"))
        if source["url"] not in claim_sources:
            issues.append(f"Sentence {index}: {source_id} does not support its selected claim_ids")
        if attribution and sentence.get("claim_ids") and source["url"] in claim_sources:
            used.add(source["url"])
    if len(used) < required:
        issues.append(f"Speak and characterize {required} distinct verified source URL(s), each tied to its claim. Make the source part of the story, not a citation roll call")
    return issues
