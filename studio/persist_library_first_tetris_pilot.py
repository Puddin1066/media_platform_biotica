"""Persist rendered library-first pilot to R2."""
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
import media_store
video=ROOT/"remotion/out/library-first-tetris.mp4"
if not video.is_file(): raise SystemExit("Rendered pilot missing")
record=media_store.persist(video,"satoshi/episodes/library-first-tetris/library-first-tetris-v1.mp4")
out=ROOT/"outputs/library-first-pilot/final-result.json"
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(record,indent=2)+"\n")
print(json.dumps(record,indent=2))
