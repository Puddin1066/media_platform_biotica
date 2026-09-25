"""Build a valid research case from a free-form Satoshi topic."""
import re
from studio import validate

CANON = {
    "version": 1,
    "audience": "Scientifically curious men's-health enthusiasts",
    "voice": "Satoshi Shkreli: original skeptical, witty on-camera host; precise claims, humane humor, explicit uncertainty",
    "visuals": "Direct-to-camera host with reviewed evidence receipts and clearly labeled illustrations",
    "rules": [
        "No invented interviews",
        "No synthetic archival evidence",
        "No causal conclusion from association alone",
        "No treatment advice",
        "No manufactured controversy"
    ]
}

def slug(text):
    value = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (value or "topic")[:64]

def build(topic, angle=""):
    topic = (topic or "").strip()
    angle = (angle or "").strip()
    if not 3 <= len(topic) <= 300:
        raise ValueError("Topic must contain 3–300 characters")
    question = topic if topic.endswith("?") else "What does the best current evidence show about " + topic + "?"
    hypotheses = [
        {"id": "H1", "statement": "The apparent effect is real and materially important", "status": "untested",
         "next_test": "Find the strongest human evidence and quantify the outcome"},
        {"id": "H2", "statement": "The apparent effect is smaller or more conditional than headlines imply", "status": "untested",
         "next_test": "Look for population, dose, timing, measurement, and confounding limits"},
        {"id": "H3", "statement": "Alternative explanations account for part of the observation", "status": "untested",
         "next_test": "Seek contrary findings, null studies, and plausible competing mechanisms"},
        {"id": "H4", "statement": "The evidence is too immature for a strong conclusion", "status": "untested",
         "next_test": "Identify what decisive study or measurement is still missing"},
    ]
    packet = {
        "id": "topic-" + slug(topic),
        "revision": 1,
        "question": question,
        "canon": {**CANON, "requested_angle": angle or "none"},
        "sources": [],
        "claims": [],
        "hypotheses": hypotheses,
    }
    return validate(packet)
