# Media text generation

## Primary path: web-search drafting

Media narration is drafted with **OpenAI Responses `web_search` as the primary
evidence mechanism**. Use `produce.py` for shorts, podcast segments, newsletters
and treatments. The model must search the live web for the case question and
competing hypotheses, then return a five-beat mystery script whose segment
`source_urls` are limited to URLs actually cited by that search.

```sh
python3 produce.py --format short
python3 produce.py --from-hypotheses --format podcast
```

Those commands are free dry runs: they validate the case/plan and report the
request identity without calling the API. The public men's-health seed works
here because produce does not require pre-cleared claim excerpts.

Live drafting additionally needs `OPENAI_API_KEY`, `OPENAI_LIVE_ENABLED=true`,
`--live`, a cumulative `--budget-usd`, and an operator-chosen
`--max-usd-per-run` reservation (worst-case allowance for tool use plus draft,
not a provider quote):

```sh
python3 produce.py --live --format short --budget-usd BUDGET --max-usd-per-run RESERVATION
```

`--max-tool-calls` defaults to 6 (range 1–8). Ambiguous failures retain their
reservation and are never auto-retried. Success writes `draft.json` and
`script.md` under `outputs/produce/` with `status: review_required` and
`publishable: false`. Structural checks enforce ordered beats and citation
membership; they do not prove scientific validity, study quality, or rights
clearance. Human review is mandatory before any production use.

Web ranking can hide negative or obscure findings. Prefer opening the cited
primary documents before promoting any line into a reviewed case packet.

## Provider roles (owner requirement)

| Capability | Provider |
| --- | --- |
| Narrative, scripts, spoken-language editing | OpenAI (web_search primary) |
| Still-image generation | OpenAI permitted |
| Video generation and performance animation | Runway |
| Speech, audio and sound generation | Runway |

Do not silently route audio or video to OpenAI. If a required Runway capability
is unavailable via its API, report the specific blocker. Image and Runway
adapters are not implemented in this milestone.

## Secondary path: reviewed claim packets

`writer.py` remains available when a human has already cleared source excerpts
and entered reviewed claims into a case packet. It does **not** call web_search;
it only narrates supplied evidence. Prefer `produce.py` whenever new discovery
is needed for media text.

Input for `writer.py`:
- Reviewed claims: `text`, `reviewer`, `limitations`, known `source_ids`.
- Sources: `url`, `locator`, `excerpt`, `rights_status` of `permitted` or `public_domain`.

```sh
python3 writer.py --case /private/path/reviewed-case.json --format short
```

The existing men's-health seed intentionally fails this check: it contains no
reviewed evidence. Tests use conspicuously fictional evidence, not medical facts.

Live writing still requires `--live`, `OPENAI_LIVE_ENABLED=true`,
`OPENAI_API_KEY`, `--budget-usd`, and verified per-million token prices. Spend
reservations live in `outputs/writing/ledger.sqlite` (separate from produce).

## Related discovery tools

- `web_research.py` — hypothesis-scoped search memos without drafting narration
- `research.py` — optional Europe PMC specialist connector
- `analyst.py` — optional triage of cleared abstracts

None of those replace `produce.py` for media text. See RESEARCH.md.

## Remote status and limitations

The public GitHub preview workflow still makes zero paid calls. No paid produce
or writing workflow is enabled in CI: private persistent draft storage and a
persistent ledger must exist first. No credentials have been read or tested in
this milestone.

References:
- https://developers.openai.com/api/docs/quickstart
- https://developers.openai.com/api/docs/guides/tools-web-search
- https://developers.openai.com/api/docs/guides/structured-outputs
