# Research loop

## Default: automated web search

`web_research.py` is the broad discovery path. It gives the OpenAI Responses API
the built-in `web_search` tool and runs one bounded investigation for each planned
hypothesis. The resulting evidence memo retains both inline-cited URLs and the
provider's broader consulted-source list. It is appropriate for finding papers,
registries, patents, reporting and other primary documents without maintaining a
separate connector for every source class.

```sh
python web_research.py
```

That command is a free dry run: it validates the case and plan and reports the
number of planned searches without making an API call. A live run requires a
fresh private `OPENAI_API_KEY`, `OPENAI_LIVE_ENABLED=true`, and explicit spending
reservations:

```sh
python web_research.py --live --budget-usd BUDGET --max-usd-per-search RESERVATION
```

`BUDGET` is the cumulative ceiling recorded in the local output directory;
`RESERVATION` is an operator-selected worst-case allowance for each search, not a
provider price quote. Verify current model and tool pricing before choosing both.
The default is four tool calls per hypothesis; `--max-tool-calls` accepts 1–8.
The plan accepts 1–8 hypotheses. Provider failures retain their reservation and
are not retried automatically because an ambiguous failure may still have spent
money. Outputs are immutable local snapshots marked `human_review_required` and
`publishable: false`.

Web search improves breadth, but it does not establish study validity, source
rights, causal inference or medical truth. Search ranking can also hide negative
or obscure findings. A reviewer must open the cited primary sources, assess study
design and exact claims, and enter approved evidence into a revised case packet
before the writing stage can use it. The platform deliberately does not convert a
search memo directly into narration.

## Optional specialist connector: Europe PMC

The first connector searches Europe PMC and retrieves bibliographic metadata and
available abstracts, including PubMed-indexed records. It does not retrieve full
texts, clinical-trial registries, patents, general web pages or paywalled content.
This is bounded discovery, not a systematic review or an autonomous fact checker.

```sh
python research.py collect --page-size 3
```

The public seed plan contains four searches tied to competing hypotheses. Each
run writes an immutable evidence snapshot and editable review template under
`outputs/research/`. Query provenance, retrieval time, source identifiers,
reported licenses and correction links are retained. PMID/DOI matches deduplicate
records across searches. Missing abstracts remain empty; provider failures fail
the run. Up to eight searches and 25 results each are allowed, first page only.
Rerunning collection makes new network requests and a new timestamped snapshot.
Completed snapshots can be reviewed repeatedly offline without fetching again.

Copy the review template before editing. For each relevant paper/hypothesis pair,
enter `supports`, `challenges` or `unclear`, an exact abstract quotation, rationale,
limitations, reviewer, next discriminating test and optional next search query.
Leave unassessed pairs `unreviewed`.

```sh
python research.py review --bundle outputs/research/BUNDLE.json --review outputs/research/MY_REVIEW.json
python research.py collect --plan outputs/research/NEXT_PLAN.json
```

Replace uppercase filenames with the paths printed by the previous command. An
empty next plan means there are no proposed searches; do not run collection on
it. Larger next plans must be split into batches of eight. Partial reviews are
allowed and remaining links are counted. Structural checks verify source links
and exact quotations; they cannot verify interpretation or causal validity.
No case claims or hypothesis statuses are automatically changed or approved.

## Optional OpenAI triage of selected abstracts

`analyst.py` can propose evidence relationships and next tests. First copy the
bundle and review the processing rights of each source. Explicitly set
`rights_status` to `permitted` or `public_domain` only when justified; reported
open-access status alone does not grant all reuse rights. Changes produce a new
snapshot hash, so reviews of the earlier snapshot cannot be applied to it.

```sh
python analyst.py --bundle outputs/research/CLEARED_BUNDLE.json
```

Default execution is a dry run. Live analysis additionally needs environment
variables `OPENAI_API_KEY` and `OPENAI_LIVE_ENABLED=true`, `--live`,
`--budget-usd`, `--input-usd-per-million` and `--output-usd-per-million` with current
verified prices. It uses the writer's single-attempt spend ledger and defaults to
the same output directory, so those default jobs share a cumulative estimated
budget. Custom output directories have separate ledgers, not an account-wide cap.
Failures keep their reservations and are never automatically retried. No live
OpenAI analysis has been verified in this milestone. No Runway credits are used.

Model suggestions are attributed as MODEL TRIAGE and require human review. The
printed review path can be copied, reviewed and passed to `research.py review`.
Quotes and IDs are checked, but a model can still misinterpret correct quotations.
Human-approved claims must be explicitly entered in a revised case packet with
reviewer, limitations and source excerpts before the writing adapter accepts them
(see WRITING.md). This handoff is currently manual.

## Privacy and publication

Europe PMC queries are sent to Europe PMC. Automated web-search queries and live
triage send the supplied case context to OpenAI with `store=false`; that is not a
promise of zero provider retention.
Research snapshots and drafts stay in the ignored local `outputs/` directory.
Do not upload them as public CI artifacts or commit them. Private remote storage
is still unimplemented, so back them up to your own private storage. Abstracts
are research material, not automatically cleared narration or republication.

Provider reference: https://europepmc.org/RestfulWebService
Endpoint: https://www.ebi.ac.uk/europepmc/webservices/rest/search

OpenAI reference: https://developers.openai.com/api/docs/quickstart
