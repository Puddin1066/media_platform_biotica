import json, os, urllib.request, urllib.error

key = os.environ.get("OPENAI_API_KEY")
if not key:
    raise SystemExit("missing OPENAI_API_KEY")
payload = {"model": "gpt-5.6-luna", "input": "Return exactly: OK"}
req = urllib.request.Request(
    "https://api.openai.com/v1/responses",
    data=json.dumps(payload).encode(),
    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read().decode())
        print("probe_status=success")
        print("model=" + str(data.get("model")))
except urllib.error.HTTPError as e:
    body = e.read().decode(errors="replace")
    print(f"probe_status=http_{e.code}")
    print(body[:1200])
    raise
