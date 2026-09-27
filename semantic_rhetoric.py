"""Semantic index, clustering, retrieval and blinded rhetoric benchmark.

This operates only on neutralized mechanics produced by huberman_pilot.py. It never
indexes raw transcript text and never asks a model to imitate a creator's voice.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path

from corpus_embeddings import _openai_json, embed_texts
from openai_models import model_for, reasoning_for

RESPONSES_ENDPOINT = "https://api.openai.com/v1/responses"
DEFAULT_DIMENSIONS = int(os.environ.get("OPENAI_EMBED_DIMENSIONS", "768"))
DEFAULT_CLUSTER_THRESHOLD = float(os.environ.get("RHETORIC_CLUSTER_THRESHOLD", "0.88"))
DIMENSIONS = ("hook_strength", "coherence", "evidence_handling", "originality", "audience_fit")

SYNTHETIC_BRIEFS = [
    {
        "id": "B01",
        "topic": "A hypothetical wearable claims to predict next-day testosterone from sleep data",
        "evidence": "Synthetic test evidence: a small validation set shows moderate correlation, but calibration worsens in shift workers and no clinical outcomes were measured.",
    },
    {
        "id": "B02",
        "topic": "A hypothetical male-fertility home test becomes much cheaper",
        "evidence": "Synthetic test evidence: analytical precision improves and price falls sharply, but the test measures only one semen parameter and cannot diagnose infertility by itself.",
    },
    {
        "id": "B03",
        "topic": "A hypothetical cold-exposure study reports a short-lived hormone change",
        "evidence": "Synthetic test evidence: the hormone rises for two hours after exposure, while the study does not show muscle gain, fat loss, fertility improvement, or long-term benefit.",
    },
    {
        "id": "B04",
        "topic": "A hypothetical hair-loss treatment works well on average but not for everyone",
        "evidence": "Synthetic test evidence: the randomized trial shows a meaningful average density gain, with wide individual variation and more discontinuations from side effects in the active arm.",
    },
    {
        "id": "B05",
        "topic": "A hypothetical sleep intervention improves one marker of metabolic health",
        "evidence": "Synthetic test evidence: a crossover experiment improves morning glucose after one week, but sample size is small and the study does not establish durable weight or cardiovascular effects.",
    },
    {
        "id": "B06",
        "topic": "A hypothetical prostate-screening algorithm reduces unnecessary follow-up",
        "evidence": "Synthetic test evidence: retrospective testing shows fewer false positives at similar sensitivity, but prospective clinical utility and performance across demographic groups remain unproven.",
    },
]


def _require_live() -> str:
    if os.environ.get("OPENAI_LIVE_ENABLED") != "true":
        raise ValueError("OPENAI_LIVE_ENABLED must be true")
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise ValueError("OPENAI_API_KEY missing")
    return key


def load_mechanics(source_dir: Path) -> list[dict]:
    rows = []
    for path in sorted(source_dir.glob("*.mechanics.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc.get("source_text_included") is not False or doc.get("creator_voice_imitation") is not False:
            raise ValueError(f"Unsafe mechanics document: {path.name}")
        for index, item in enumerate(doc.get("mechanics", [])):
            if set(item) != {"function", "mechanic", "when_to_use", "avoid"}:
                raise ValueError(f"Unexpected mechanic schema in {path.name}")
            rows.append({"episode_id": doc["episode_id"], "mechanic_index": index, **item})
    if not rows:
        raise ValueError("No neutralized mechanics found")
    return rows


def mechanic_text(row: dict) -> str:
    return "\n".join([
        f"function: {row['function']}",
        f"mechanic: {row['mechanic']}",
        f"when to use: {row['when_to_use']}",
        f"avoid: {row['avoid']}",
    ])


def _norm(v: list[float]) -> float:
    return math.sqrt(sum(x * x for x in v))


def cosine(a: list[float], b: list[float]) -> float:
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return 0.0
    return sum(x * y for x, y in zip(a, b)) / (na * nb)


def build_index(source_dir: Path, model: str | None = None, dimensions: int = DEFAULT_DIMENSIONS) -> dict:
    key = _require_live()
    model = model or model_for("embedding")
    rows = load_mechanics(source_dir)
    texts = [mechanic_text(row) for row in rows]
    vectors = []
    for start in range(0, len(texts), 64):
        vectors.extend(embed_texts(texts[start:start + 64], model, dimensions, key))
    items = []
    for i, (row, vector) in enumerate(zip(rows, vectors), 1):
        items.append({"id": f"M{i:03d}", **row, "embedding": vector})
    return {
        "schema_version": 1,
        "source_policy": "huberman_lab_solo_only",
        "source_text_included": False,
        "creator_voice_imitation": False,
        "embedding_model": model,
        "embedding_dimensions": dimensions,
        "mechanic_count": len(items),
        "items": items,
    }


def semantic_clusters(index: dict, threshold: float = DEFAULT_CLUSTER_THRESHOLD) -> list[dict]:
    clusters = []
    for item in index["items"]:
        best = None
        best_score = -1.0
        for cluster in clusters:
            score = cosine(item["embedding"], cluster["representative"]["embedding"])
            if score > best_score:
                best, best_score = cluster, score
        if best is not None and best_score >= threshold:
            best["members"].append(item["id"])
            best["max_member_similarity"] = max(best["max_member_similarity"], round(best_score, 6))
        else:
            clusters.append({
                "cluster_id": f"S{len(clusters)+1:03d}",
                "representative": item,
                "members": [item["id"]],
                "max_member_similarity": 1.0,
            })
    return clusters


def retrieve(index: dict, query: str, top_k: int = 6) -> list[dict]:
    key = _require_live()
    qvec = embed_texts([query], index["embedding_model"], index["embedding_dimensions"], key)[0]
    ranked = []
    for item in index["items"]:
        ranked.append({"score": cosine(qvec, item["embedding"]), **{k: v for k, v in item.items() if k != "embedding"}})
    ranked.sort(key=lambda row: row["score"], reverse=True)
    return ranked[:max(1, top_k)]


def _response_text(model: str, instructions: str, prompt: str, key: str, reasoning: str | None = None) -> str:
    body = {"model": model, "store": False, "instructions": instructions, "input": prompt, "max_output_tokens": 700}
    if reasoning:
        body["reasoning"] = {"effort": reasoning}
    result = _openai_json(RESPONSES_ENDPOINT, body, key)
    if result.get("status") != "completed":
        raise ValueError("Response incomplete")
    text = "".join(
        part.get("text", "")
        for item in result.get("output", []) if item.get("type") == "message"
        for part in item.get("content", []) if part.get("type") == "output_text"
    ).strip()
    if not text:
        raise ValueError("No response text")
    return text


def _script_prompt(brief: dict, mechanics: list[dict] | None) -> str:
    extra = ""
    if mechanics:
        formatted = []
        for m in mechanics:
            formatted.append(f"- {m['function']}: {m['mechanic']} | avoid: {m['avoid']}")
        extra = "\n\nTransferable rhetorical mechanics you may use selectively:\n" + "\n".join(formatted)
    return (
        f"TOPIC: {brief['topic']}\nEVIDENCE: {brief['evidence']}\n\n"
        "Write a 70-90 word short-form monologue for Satoshi Shkreli / Biotica Media. "
        "Audience: skeptical, technically minded men 25-50. Start with the consequence or contradiction, not a greeting. "
        "Use only the synthetic evidence supplied here; do not add real-world medical claims, citations, names, or numbers. "
        "Make the uncertainty explicit without draining the hook. End with a crisp implication, not medical advice. "
        "Do not mention rhetorical mechanics, Huberman, or any source persona."
        + extra
    )


def generate_candidate(brief: dict, mechanics: list[dict] | None, key: str) -> str:
    return _response_text(
        model_for("writing"),
        "Write original Biotica Media copy in the Satoshi Shkreli brand voice. Do not imitate any real creator or reuse distinctive phrasing.",
        _script_prompt(brief, mechanics),
        key,
        reasoning_for("writing"),
    )


def _judge(brief: dict, a: str, b: str, key: str) -> dict:
    schema = {
        "type": "object", "additionalProperties": False,
        "required": ["A", "B", "preferred"],
        "properties": {
            "A": {"type": "object", "additionalProperties": False, "required": list(DIMENSIONS), "properties": {d: {"type": "number", "minimum": 1, "maximum": 5} for d in DIMENSIONS}},
            "B": {"type": "object", "additionalProperties": False, "required": list(DIMENSIONS), "properties": {d: {"type": "number", "minimum": 1, "maximum": 5} for d in DIMENSIONS}},
            "preferred": {"type": "string", "enum": ["A", "B", "tie"]},
        },
    }
    body = {
        "model": model_for("editorial_reasoning"),
        "store": False,
        "reasoning": {"effort": reasoning_for("editorial_reasoning") or "high"},
        "instructions": "Act as a blind editorial evaluator. Score only writing quality against the supplied brief. Do not infer which candidate used retrieval.",
        "input": f"TOPIC: {brief['topic']}\nEVIDENCE: {brief['evidence']}\n\nCANDIDATE A:\n{a}\n\nCANDIDATE B:\n{b}",
        "max_output_tokens": 500,
        "text": {"format": {"type": "json_schema", "name": "rhetoric_benchmark_score", "strict": True, "schema": schema}},
    }
    result = _openai_json(RESPONSES_ENDPOINT, body, key)
    if result.get("status") != "completed":
        raise ValueError("Judge response incomplete")
    raw = "".join(
        p.get("text", "")
        for item in result.get("output", []) if item.get("type") == "message"
        for p in item.get("content", []) if p.get("type") == "output_text"
    )
    return json.loads(raw)


def run_benchmark(index: dict, top_k: int = 6) -> dict:
    key = _require_live()
    trials = []
    totals = {"none": {d: [] for d in DIMENSIONS}, "semantic": {d: [] for d in DIMENSIONS}}
    wins = {"none": 0, "semantic": 0, "tie": 0}
    for brief in SYNTHETIC_BRIEFS:
        selected = retrieve(index, brief["topic"] + " " + brief["evidence"], top_k=top_k)
        baseline = generate_candidate(brief, None, key)
        semantic = generate_candidate(brief, selected, key)
        swap = int(hashlib.sha256(brief["id"].encode()).hexdigest(), 16) % 2 == 0
        a, b = (semantic, baseline) if swap else (baseline, semantic)
        labels = {"A": "semantic", "B": "none"} if swap else {"A": "none", "B": "semantic"}
        judged = _judge(brief, a, b, key)
        for blind in ("A", "B"):
            arm = labels[blind]
            for d in DIMENSIONS:
                totals[arm][d].append(float(judged[blind][d]))
        pref = judged["preferred"]
        wins["tie" if pref == "tie" else labels[pref]] += 1
        trials.append({
            "brief_id": brief["id"], "topic": brief["topic"], "evidence": brief["evidence"],
            "retrieved": [{k: m[k] for k in ("id", "episode_id", "mechanic_index", "function", "mechanic", "score")} for m in selected],
            "baseline_script": baseline, "semantic_script": semantic,
            "blind_order": labels, "judge": judged,
        })
    means = {arm: {d: sum(vals) / len(vals) for d, vals in dims.items()} for arm, dims in totals.items()}
    overall = {arm: sum(means[arm].values()) / len(DIMENSIONS) for arm in means}
    delta = overall["semantic"] - overall["none"]
    promoted = delta >= 0.15 and means["semantic"]["originality"] >= means["none"]["originality"] - 0.10 and means["semantic"]["evidence_handling"] >= means["none"]["evidence_handling"] - 0.10
    return {
        "schema_version": 1,
        "briefs_are_synthetic": True,
        "arms": ["none", "semantic"],
        "dimensions": list(DIMENSIONS),
        "top_k": top_k,
        "means": means,
        "overall": overall,
        "semantic_delta": delta,
        "wins": wins,
        "promotion_rule": "semantic overall >= baseline +0.15 with no >0.10 drop in originality or evidence handling",
        "promoted": promoted,
        "trials": trials,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-dir", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--cluster-threshold", type=float, default=DEFAULT_CLUSTER_THRESHOLD)
    p.add_argument("--top-k", type=int, default=6)
    args = p.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    index = build_index(Path(args.source_dir))
    clusters = semantic_clusters(index, args.cluster_threshold)
    index_path = out / "semantic-index.json"
    index_path.write_text(json.dumps(index) + "\n", encoding="utf-8")
    cluster_report = {
        "mechanic_count": index["mechanic_count"],
        "cluster_threshold": args.cluster_threshold,
        "cluster_count": len(clusters),
        "semantic_deduplicated_count": index["mechanic_count"] - len(clusters),
        "clusters": [{"cluster_id": c["cluster_id"], "representative_id": c["representative"]["id"], "members": c["members"], "max_member_similarity": c["max_member_similarity"]} for c in clusters],
    }
    (out / "semantic-clusters.json").write_text(json.dumps(cluster_report, indent=2) + "\n", encoding="utf-8")
    benchmark = run_benchmark(index, args.top_k)
    (out / "semantic-benchmark.json").write_text(json.dumps(benchmark, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "mechanics": index["mechanic_count"],
        "semantic_clusters": len(clusters),
        "semantic_deduplicated": index["mechanic_count"] - len(clusters),
        "benchmark_delta": benchmark["semantic_delta"],
        "promoted": benchmark["promoted"],
        "wins": benchmark["wins"],
    }, indent=2))


if __name__ == "__main__":
    main()
