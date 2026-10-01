"""Contracts for a company-specific Opportunity Brief in Satoshi Studio.

An outreach brief is a private review artifact, never an Instagram release.
The format reuses the ordinary Studio stages and the claim ledger; this module
only validates intake and builds a shareable, source-linked companion note.
"""
from __future__ import annotations

from urllib.parse import urlparse


FORMAT = "opportunity_brief"


def is_brief(request):
    return (request.get("format") or {}).get("id") == FORMAT


def context(request):
    if not is_brief(request):
        raise ValueError("Expected opportunity_brief format")
    target = request.get("opportunity") or {}
    company = str(target.get("company") or "").strip()
    role = str(target.get("role") or "").strip()
    question = str(target.get("decision_question") or "").strip()
    if not all([company, role, question]):
        raise ValueError("Opportunity Brief requires company, role and decision_question")
    if max(map(len, [company, role, question])) > 500:
        raise ValueError("Opportunity Brief context is too long")
    url = str(target.get("job_url") or "").strip()
    if url and (urlparse(url).scheme != "https" or not urlparse(url).netloc):
        raise ValueError("job_url must be an HTTPS URL")
    return {"company": company, "role": role, "decision_question": question,
            "job_url": url, "candidate": str(target.get("candidate") or "Jay").strip()[:80]}


def source_brief(script, request):
    """Keep cited sentences attached to actual research URLs for review."""
    target = context(request)
    cited = [{"text": s["text"], "claim_ids": s.get("claim_ids", []),
              "sources": s.get("citations", [])} for s in script["script"] if s.get("citations")]
    return {"format": FORMAT, "company": target["company"], "role": target["role"],
            "decision_question": target["decision_question"], "job_url": target["job_url"],
            "title": script["title"], "thesis": script["thesis"], "cited_points": cited,
            "status": "draft_requires_candidate_review"}


def outreach_draft(script, request, video_url):
    """Produce a concise, unsent note; never claim a relationship or past result."""
    target = context(request)
    return {"format": FORMAT, "status": "draft_not_sent", "company": target["company"],
            "role": target["role"], "video_url": video_url,
            "subject": f"A brief thought on {target['company']}'s {target['decision_question'][:65]}",
            "body": (f"Hello,\n\nI applied for the {target['role']} role and took a closer look at "
                     f"{target['decision_question']} I made a short, sourced brief with one "
                     f"interpretation and a practical next step: {video_url}\n\n"
                     f"If useful, I'd welcome a conversation.\n\n{target['candidate']}"),
            "review": ["Check the role and recipient before sending", "Verify claims and source links",
                       "Review voice, visual identity and video sharing permissions"]}
