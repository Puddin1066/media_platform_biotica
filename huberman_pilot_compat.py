import argparse
from pathlib import Path
import huberman_mechanics_extract as hme
import huberman_pilot

_original = hme._request_payload

def _compat_payload(source_text: str, episode_id: str) -> dict:
    payload = _original(source_text, episode_id)
    payload.pop("text", None)
    return payload

hme._request_payload = _compat_payload

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=1)
    p.add_argument("--output-dir", default="artifacts/huberman-pilot")
    args = p.parse_args()
    report = huberman_pilot.run(args.limit, Path(args.output_dir))
    failed = [x for x in report["episodes"] if x.get("status") != "success"]
    if failed:
        raise SystemExit(f"Pilot failed for {len(failed)} episode(s)")
