# Persona integration boundary

The generic Satoshi short pipeline is:

`requests/satoshi/current.json -> satoshi_supervisor.py -> satoshi_short.py -> produce.py -> narrative_mode.py/reference_corpus.py -> researched draft -> unreviewed_video_preview.py -> Runway -> Remotion -> render_audio_guard.py -> persist_media.py/R2`.

The Satoshi persona is part of the writing contract, not a post-processing style pass. `writing_contract.py` hashes the persona contract, prompt-producing code, narrative routing, corpus profile and corpus exemplars. The supervisor includes that digest in request identity so a writing-contract change invalidates stale researched drafts and rendered previews.

The production workflow watches those writing-contract paths, and unit tests assert that the persona exemplar is selected first in argumentative, explanatory and discovery modes.

The dedicated TRT pilot path remains a locked-script special case. It does not become persona-aware merely because the generic short writer changes; a TRT v2 script must be regenerated or explicitly relocked through the generic persona-aware writing stage before another final render.
