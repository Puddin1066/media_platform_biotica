Review focus:
- `writing_contract.py` hashes every file that can materially alter generic Satoshi short writing.
- `satoshi_supervisor.py` includes that hash in request identity and invalidates stale drafts/rendered previews on change.
- `satoshi_short.py` records the hash in manifests/review briefs.
- `produce-satoshi-video-preview.yml` watches persona, prompt, routing and corpus changes.
- tests prove persona exemplar selection for all three narrative modes and request-ID invalidation.
- no automatic publication behavior is added.
