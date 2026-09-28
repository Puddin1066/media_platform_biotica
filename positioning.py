"""Validate men's-health audience positioning before a Satoshi script can pass."""

TERRITORIES = {
    "hormones_performance",
    "fertility_reproductive",
    "sexual_function",
    "appearance_body",
    "longevity_diagnostics",
    "emerging_weird_science",
}
HOOK_TYPES = {"threat_tradeoff", "optimization", "conflict", "hidden_tradeoff", "counterintuitive_receipt"}

def _text(value, name, low=4, high=500):
    if not isinstance(value, str) or not low <= len(value.strip()) <= high:
        raise ValueError(name + " must be substantive text")
    return value.strip()

def _metadata_text(value, name, fallback=None, high=500):
    if value is None or (isinstance(value, str) and not value.strip()):
        if fallback is not None:
            return fallback
        raise ValueError(name + " must be metadata text")
    if not isinstance(value, str) or len(value.strip()) > high:
        raise ValueError(name + " must be concise metadata text")
    return value.strip()

def validate(value, cited_urls):
    if not isinstance(value, dict):
        raise ValueError("positioning object required")
    required = {
        "territory", "male_consequence", "prevailing_belief", "evidence_conflict",
        "evidence_receipt", "evidence_receipt_url", "audience_tension",
        "share_trigger", "positioned_premise", "hook_variants"
    }
    if set(value) != required:
        raise ValueError("Invalid positioning fields")
    if value["territory"] not in TERRITORIES:
        raise ValueError("Unknown men's-health content territory")
    consequence = _metadata_text(
        value["male_consequence"],
        "male_consequence",
        fallback="unspecified_male_relevance",
    )
    for field in (
        "prevailing_belief", "evidence_conflict", "evidence_receipt",
        "audience_tension", "share_trigger", "positioned_premise"
    ):
        _text(value[field], field)
    url = value["evidence_receipt_url"]
    if not isinstance(url, str) or url not in set(cited_urls):
        raise ValueError("Positioning receipt must use a web-search cited URL")
    hooks = value["hook_variants"]
    if not isinstance(hooks, list) or len(hooks) != 3:
        raise ValueError("Exactly three audience-positioned hook variants required")
    seen = set()
    for hook in hooks:
        if not isinstance(hook, dict) or set(hook) != {"type", "text"}:
            raise ValueError("Each hook needs exactly type + text")
        if hook["type"] not in HOOK_TYPES:
            raise ValueError("Unknown hook type")
        text = _text(hook["text"], "hook", 6, 180)
        if text.lower() in seen:
            raise ValueError("Hook variants must be materially distinct")
        seen.add(text.lower())
    return {
        "status": "pass",
        "territory": value["territory"],
        "male_consequence": consequence,
        "hooks": len(hooks),
        "publishable": False,
    }
