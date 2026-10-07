from __future__ import annotations
import json, os, urllib.request, urllib.error
from pathlib import Path

ENDPOINT="https://api.openai.com/v1/responses"

def _text(result):
    chunks=[]
    for item in result.get("output",[]):
        if item.get("type")=="message":
            for c in item.get("content",[]):
                if c.get("type")=="output_text": chunks.append(c.get("text",""))
    return "".join(chunks).strip()

def plan(request,output):
    key=os.environ.get("OPENAI_API_KEY")
    if not key: raise ValueError("OPENAI_API_KEY required")
    prompt="""You are the sole editorial planner for Satoshi Reels. Research and plan one 45-70 second Reel.
Return one JSON object only. It must contain episode_id,title,topic,scene,publications,beats.
scene requires environment,wardrobe,framing. Satoshi should be seated or physically anchored in a topic-relevant world.
Each beat requires id,text,kind (host|evidence), visual. Host beats should be 3-6 seconds spoken and appear only for persona-bearing moments.
Evidence beats should use visual.type publication|typography|illustration and publication_ref when applicable.
Use strong primary evidence, preserve the user's memorable phrasing, dry humor, and one clear thesis. Do not create production state.
"""
    body={"model":os.environ.get("SATOSHI_V2_PLANNER_MODEL","gpt-5.6-sol"),"store":False,
          "instructions":prompt,"input":json.dumps(request,ensure_ascii=False),
          "tools":[{"type":"web_search"}],"tool_choice":"auto","max_output_tokens":7000,
          "reasoning":{"effort":"high"}}
    req=urllib.request.Request(ENDPOINT,data=json.dumps(body).encode(),
        headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"},method="POST")
    try:
        with urllib.request.urlopen(req,timeout=300) as r: result=json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Planner HTTP {e.code}: "+e.read(2000).decode(errors="replace")) from None
    text=_text(result)
    try: episode=json.loads(text)
    except json.JSONDecodeError:
        episode=json.loads(text[text.find("{"):text.rfind("}")+1])
    Path(output).parent.mkdir(parents=True,exist_ok=True)
    Path(output).write_text(json.dumps(episode,indent=2,ensure_ascii=False)+"\n")
    return episode
