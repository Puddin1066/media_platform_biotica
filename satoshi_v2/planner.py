from __future__ import annotations
import json, os, urllib.request, urllib.error
from pathlib import Path

ENDPOINT="https://api.openai.com/v1/responses"

def _text(result):
    chunks=[]
    for item in result.get("output",[]):
        if item.get("type")=="message":
            for c in item.get("content",[]):
                if c.get("type")=="output_text":
                    chunks.append(c.get("text",""))
    return "".join(chunks).strip()

def _parse_json(text):
    if not text:
        raise ValueError("Planner returned no output text")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        left,right=text.find("{"),text.rfind("}")
        if left < 0 or right <= left:
            raise ValueError("Planner returned no JSON object")
        return json.loads(text[left:right+1])

def plan(request,output):
    key=os.environ.get("OPENAI_API_KEY")
    if not key:
        raise ValueError("OPENAI_API_KEY required")
    prompt="""You are the sole editorial planner for Satoshi Reels. Research and plan one 45-70 second Reel.
Return one compact JSON object only. It must contain episode_id,title,topic,scene,publications,beats.
scene requires environment,wardrobe,framing. Satoshi should be seated or physically anchored in a topic-relevant world.
Each beat requires id,text,kind (host|evidence), visual. Host beats should be 3-6 seconds spoken and appear only for persona-bearing moments.
Evidence beats should use visual.type publication|typography|illustration and publication_ref when applicable.
Use strong primary evidence, preserve the user's memorable phrasing, dry humor, and one clear thesis.
Distinguish established standard of care from investigational technology. Do not create production state.
Keep the JSON compact enough to complete reliably."""
    last=None
    for attempt in range(2):
        body={
            "model":os.environ.get("SATOSHI_V2_PLANNER_MODEL","gpt-5.6-sol"),
            "store":False,
            "instructions":prompt + ("" if attempt==0 else " Previous attempt did not return complete JSON. Return a shorter complete JSON object now."),
            "input":json.dumps(request,ensure_ascii=False),
            "tools":[{"type":"web_search"}],
            "tool_choice":"auto",
            "max_output_tokens":9000 if attempt==0 else 14000,
            "reasoning":{"effort":"medium" if attempt==0 else "low"},
        }
        req=urllib.request.Request(
            ENDPOINT,data=json.dumps(body).encode(),
            headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"},
            method="POST")
        try:
            with urllib.request.urlopen(req,timeout=300) as r:
                result=json.loads(r.read())
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"Planner HTTP {e.code}: "+e.read(2000).decode(errors="replace")) from None
        status=result.get("status")
        text=_text(result)
        if status not in (None,"completed"):
            detail=(result.get("incomplete_details") or {}).get("reason") or status
            last=RuntimeError(f"Planner response incomplete: {detail}")
            continue
        try:
            episode=_parse_json(text)
            Path(output).parent.mkdir(parents=True,exist_ok=True)
            Path(output).write_text(json.dumps(episode,indent=2,ensure_ascii=False)+"\n")
            return episode
        except (ValueError,json.JSONDecodeError) as exc:
            last=exc
    raise last or RuntimeError("Planner failed without a usable response")
