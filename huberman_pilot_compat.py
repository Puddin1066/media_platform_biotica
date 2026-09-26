import argparse
import json
from pathlib import Path
import huberman_mechanics_extract as hme
import huberman_pilot

_original_payload = hme._request_payload
_original_response_text = hme._response_text


def _compat_payload(source_text: str, episode_id: str) -> dict:
    payload = _original_payload(source_text, episode_id)
    payload.pop("text", None)
    return payload


def _first_json_value(text: str):
    decoder = json.JSONDecoder()
    candidates = [i for i, ch in enumerate(text) if ch in "[{"]
    for idx in candidates:
        try:
            value, _ = decoder.raw_decode(text[idx:])
            return value
        except json.JSONDecodeError:
            continue
    raise ValueError("No valid JSON object or array found in model output")


def _compat_response_text(response: dict) -> str:
    text = _original_response_text(response)
    parsed = _first_json_value(text)
    if isinstance(parsed, list):
        parsed = {"mechanics": parsed}
    if not isinstance(parsed, dict):
        raise ValueError("Mechanics response must decode to an object or array")
    return json.dumps(parsed)


hme._request_payload = _compat_payload
hme._response_text = _compat_response_text

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=1)
    p.add_argument("--output-dir", default="artifacts/huberman-pilot")
    args = p.parse_args()
    report = huberman_pilot.run(args.limit, Path(args.output_dir))
    failed = [x for x in report["episodes"] if x.get("status") != "success"]
    if failed:
        raise SystemExit(f"Pilot failed for {len(failed)} episode(s)")
