# Satoshi Shkreli: science-backed drama podcast specification

Status: **specification only**. This document describes the proposed tool; it
does not assert that the repository can currently produce this podcast.

## Editorial product

One investigated men's-health topic produces an original **18–22 minute pilot**
conversation between two or three voices. This is an editorial starting range,
not a measured demographic optimum. The story asks a concrete question,
follows what happened, presents competing explanations, examines primary
evidence, distinguishes what is established from what is alleged, and ends with
the practical consequence or a next test. The 30-second Reel and podcast share
the reviewed case and claim IDs, but each has its own script and editorial
approval. The podcast should never pad the Reel or imply a synthetic exchange
is a recorded interview. **The format is science-backed drama**: curiosity and
conflicting stakes give the episode its tension. A conspiracy or coordinated
scheme can be the subject when records support that characterization; it is
never the premise required of every episode.

| Persona | Function | Boundary |
| --- | --- | --- |
| Satoshi Shkreli | Host: stakes, questions, original skeptical humor, transitions. | Asks what the evidence permits; describes documented coordination precisely. |
| Rotating source author | A verified author of the episode's anchor publication, or an explicitly identified AI portrayal of that author's *published perspective*. Explains and defends what the source actually says. | Every attributed position must be traceable to the work or another approved statement by that author; do not invent private opinions, discoveries, or quotes. |
| Morgan (optional) | Curious producer or evidence challenger: translates jargon, presses for listener relevance and contrary evidence. | No fabricated reporting, interviews, or first-hand experience. |

**The source-author role is mandatory in every episode.** Start with Satoshi
and that episode's rotating author perspective. Add Morgan when a third voice
advances the story; a third voice by itself is not evidence of greater
engagement. It is a discussion of the work, not automatically an interview.

### Source-author casting contract

The episode selects an **anchor publication** and verifies the relationship
between its named person and the work. Eligible sources include a peer-reviewed
paper, preprint, blog or reported article with an attributable byline, and a
patent filing with a **named inventor**. A patent inventor is not necessarily
the applicant or assignee; label the person by their actual role and do not
imply that a patent establishes clinical effectiveness. Organizational or
anonymous posts without a verifiable natural-person author cannot fill this
role; select another anchor or pause the episode.
[USPTO on inventors, applicants and assignees](https://www.uspto.gov/sites/default/files/documents/Patents-Toolkit.pdf).

The `source_author.json` for an episode must contain: `person_name`,
`source_type`, `work_title`, `work_url`, stable identifier (DOI, patent
publication number or canonical URL), `role_on_work` (author/coauthor/inventor),
`authorship_evidence`, `relevant_passages` with locators, `published_positions`,
`known_limitations`, `publication_status` (including retraction or correction),
and `portrayal_mode`. A person named only in a citation or quoted in a blog is
not automatically its author. The writer may draw from other evidence in the
case, but only attributable statements can be put in this guest's mouth.

The casting step searches the approved case for eligible works, ranks their
authors by relevance to the episode question, strength and specificity of the
published position, verifiability of authorship, and room for a genuine
counterargument. It records the selected person and rejected candidates. The
author may support, qualify, or challenge the dramatic hypothesis; the role is
anchored to their work, not an obligation to affirm the show's thesis. The
script writer receives the verified author profile alongside the evidence
packet and generates **that episode's** guest voice, instead of reusing a
generic scientist persona.

### Episode evidence stack and spoken attribution

Before drafting, search the exact episode question for original papers and
abstracts, independent studies or reviews, original reported or authored
blogs, relevant filings, and public records. Resolve identifiers and original
URLs, verify authorship and affiliations against the actual work, check
publication status and corrections, and save the passage and locator that
supports each candidate claim. A headline about a study is not a substitute
for the study. A patent documents a filing, not proof that its proposed
mechanism works. A blog can establish its author's stated position without
becoming clinical evidence. Distinct articles describing the same study or
dataset do not count as independent confirmation.

Select **roughly three to five distinct substantive works** for a 20-minute
episode when the topic supports them: the anchor author's work, independent
context or corroboration, and a credible limitation or competing explanation.
An original business, regulatory or patent record can establish the commercial
stakes when relevant. This is an editorial range, not a quota: use fewer for a
narrow case and more for a genuinely complex one. If evidence is too thin to
support the episode's central proposition, narrow the question or stop rather
than padding the count. Store the candidate list, exclusions, overlap between
datasets, selection reasons and reviewed excerpts in `evidence_packet.json`.
Cross-check literature identifiers and publication status in
[Europe PMC](https://europepmc.org/RestfulWebService),
[PubMed](https://pubmed.ncbi.nlm.nih.gov/help/), and
[Crossref](https://www.crossref.org/documentation/retrieve-metadata/rest-api/),
then inspect the original document before approving its claim.

**Make the documents audible without reading a bibliography.** Introduce a
source where its finding changes the conversation: who actually wrote it,
what kind of work it is, when it appeared, the specific observation or
argument, and the limitation that matters. Mention a person's institution or
location only when verified and relevant. A host can say, for example,
“In [verified year], [verified author] reported [specific observation] in
[identified work]. Does that tell us *why* it happened?” The source voice can
explain its published interpretation; another speaker can test it against
independent evidence. Those brackets are required verified inputs, not lines
for the final script. The full title, DOI or canonical URL, passage locator,
and timestamp go in the transcript and show notes; spoken dialogue can use a
short, natural attribution. Never invent a researcher, place, number, quote,
or causal mechanism to enliven a scene. A correlation or proposed mechanism
must not be narrated as a demonstrated cause.

Every introduced factual proposition maps to a reviewed `claim_id` and one or
more `source_id`s, with `source_locator`, `attribution_as_spoken`,
`claim_status` (finding, allegation, inference or question), and
`qualification_as_spoken`. Log which act and turn actually communicates each
major work. Count distinct original works and independent datasets, not raw
footnotes; a citation list at the end does not replace in-conversation
attribution. The checker flags claims with missing support, invented source
details, absent qualifications, and an episode that relies on one study while
claiming a broad scientific consensus. An editor resolves these flags before
voice generation.

There are two explicit modes:

1. **Participating author:** the actual person consents, records or approves
   their own contribution, and may discuss beyond the publication. Keep a
   distinct signed approval and the real recording. Introduce them by name.
2. **Source-grounded AI portrayal:** a clearly identified synthetic voice
   represents the *published argument*, with no cloned voice or likeness and
   no suggestion that the real person recorded, endorsed, or reviewed the
   conversation. Introduce it audibly and in show notes as an AI portrayal,
   e.g., “Our source voice represents the published position of [name], an
   author of [work]; these are scripted lines, not their words.” The script
   can discuss and defend that position, but must not invent first-person
   memories, personal motives, or new views attributed to them. If the show
   needs to say “I wrote this study” as the real person, use participating-author
   mode instead.

The U.S. Copyright Office has identified unauthorized digital replicas as a
distinct concern. That is one reason the synthetic mode uses its own voice,
clear identification, and source-constrained lines rather than a cloned author
voice. [Copyright Office: digital replicas](https://copyright.gov/newsnet/2024/1048.html).

## The script is the master

The writing model first composes the **entire, self-contained episode** as a
single reviewed master script. It includes exact spoken text, explicit speaker
labels, act headings, claim IDs and optional nonspoken audio direction. The
parser then splits that *approved* script deterministically into ordered turns.
It must not ask a model to invent extra dialogue during parsing. If the draft
arrives without speaker labels, a separate casting proposal may assign voices,
but it must return for human review before generation. Changing an approved
line creates a new script revision.

### Structured story, natural conversation

The deterministic contract covers the verified evidence packet, major story
beats, speaker identity, portrayal disclosure, approved spoken text, source
trace, and the final turn order. It does **not** dictate that every turn cite a
paper or follow a rigid question-answer template. The whole-script writer may
propose digressions, brief jokes, surprise, self-correction, interruptions,
follow-up questions and callbacks when they reveal stakes or make a result
easier to understand. Give the source author's published position room to
complicate the host's hypothesis; let Morgan ask what a listener would ask.
Return from each diversion to the question and avoid repetitive banter.

At draft time, tag each passage as `evidence`, `interpretation`, `reaction`,
`humor`, or `transition`; tags can overlap. Verify new factual assertions in
*all* categories, including jokes and asides. Editorial review scores whether
the dialogue sounds like people responding to one another and whether the
sources emerge at useful moments across the acts. An approved spontaneous
sounding line remains part of the exact script for speech generation. If real
participants improvise during recording, transcribe and fact-check the new
line, approve a revised master and reassemble against that revision. A model
or voice generator cannot improvise new factual material after approval.

### OpenAI writers and model choice

**OpenAI is the writing engine**. A writer first gets the reviewed evidence
packet, the source-author profile, the versioned showrunner prompt, and the
episode brief, then drafts a whole spoken conversation; a second
pass edits that complete script for conversational flow, factual scope and
distinct speaker roles. It cannot silently introduce facts absent from the
reviewed claims. A final extraction pass assigns turn IDs and prepares audio
directions without rewriting spoken words. The two writing passes may use the
same premium model; this is an editorial workflow, not a requirement for a
fixed number of API calls.

#### Versioned showrunner persona and prompt contract

The writer's persistent background is a **senior investigative audio
showrunner and screenplay story editor with strong health-science literacy**.
This is a working role with explicit editorial responsibilities, not an
instruction to impersonate a famous producer or reproduce another show's
signature jokes, lines, catchphrases, or voice. An editor can study examples
of scene design and conversational writing, then record *transferable craft
attributes* in a versioned `podcast_writer_prompt.md`. The prompt must be
passed intact to both draft and substantive rewrite, and its version and hash
stored with the episode. The first implementation should use this actual
prompt template, with bracketed episode inputs filled from reviewed artifacts:

> **ROLE.** You are the lead writer and story editor for an original,
> investigative men's-health audio show. You can reason like a medical
> literature editor and construct scenes like a screenplay producer. You are
> curious, precise, skeptical of easy explanations, and comfortable letting
> a compelling hypothesis weaken when the evidence demands it. Write for
> technically curious listeners without assuming graduate training.
>
> **SHOW.** Satoshi Shkreli is a sharp, amused host who follows the money and
> asks concrete questions; he never substitutes insinuation for a finding.
> The rotating source voice explains the *published* perspective defined in
> `source_author.json`, under its recorded portrayal mode. Morgan, when used,
> is a perceptive listener surrogate who can interrupt to ask what a result
> means or what else might explain it. Give each person a different job,
> vocabulary and rhythm. The exchange should feel responsive, not like three
> alternating monologues or a simulated real interview.
>
> **EPISODE QUESTION.** [One answerable question and why it matters now.]
> **AUDIENCE AND LENGTH.** [Listener profile, planned duration and word range.]
> **EVIDENCE.** [Reviewed evidence_packet.json, claim ledger, source locators,
> exclusions, author profile and verified portrayal disclosure.]
> **STORY ENGINE.** Begin with one documented surprise or consequential
> scene; establish the question early. Move by discovery: a specific source
> changes what the host thinks, another complicates it, and the ending
> answers only what can be established. Use the episode's actual chronology
> when chronology matters; never invent a scene, quotation, witness or motive.
> Put roughly three to five substantive works into the conversation when
> warranted by this case. Identify each naturally at the moment its finding
> matters, then let another speaker react, probe the method or compare it to
> a conflicting source. Full references belong in the transcript and notes.
>
> **SPOKEN CRAFT.** Write for the ear: short speakable sentences, varied turn
> lengths, contractions when natural, a concrete image before an abstraction,
> a brief pause after a genuine reversal, and occasional dry humor aimed at
> an idea or institution rather than a patient. Permit a useful aside or
> interruption and return to the question. Give a speaker a reason to change
> their mind. Avoid relentless punchlines, canned cliffhangers, lecture
> paragraphs, symmetrical Q&A, and a fixed citation cadence. The tone can
> be dramatic; the facts cannot be.
>
> **FACT BOUNDARY.** Every factual assertion, including an aside or joke,
> must map to approved claim IDs and source locators. Preserve distinctions
> among observation, causal claim, allegation and unresolved question. A
> study's abstract may summarize its own result; do not infer a broader
> causal conclusion from that summary. Speak only verified names, dates,
> institutions, numbers and affiliations. Keep synthetic source-voice lines
> within the documented published position and include its disclosure.
> Mark an evidence gap for the editor instead of filling it with plausible
> detail. Do not mimic a named living writer or reproduce another show's
> recognizable material.
>
> **DELIVERABLE.** First return a one-page beat map with an evidence-bearing
> turn, emotional change and unanswered question for each act; then the
> complete spoken script with act and speaker labels, optional audio cues,
> claim IDs and source IDs on factual passages. Finally include a short
> self-critique: unearned moments, repeated explanations, weak attributions,
> unsupported lines, source-voice boundary problems, and the edits you made.
> The editor approves the full script; the parser never treats this
> self-critique as spoken dialogue.

Separate stable show identity from episode inputs. The prompt declares voice
and craft; `evidence_packet.json` supplies facts; the episode brief sets
angle, runtime and constraints; the approved script supplies exact audio text.
Test the showrunner prompt itself on the same three cases as the model
comparison, blind-reviewing naturalness, originality, factual fidelity,
speaker differentiation and listening pull. Revision requires a new prompt
version, not a quiet change to the episode's facts. Spotify describes scripts
as a foundation for a focused conversation, and Transom describes planning
scenes around a story question; neither supplies a universal celebrity-writer
persona that can be pasted into a prompt.
[Spotify: podcast scripting](https://creators.spotify.com/resources/create/how-to-write-podcast-scripts) ·
[Transom: thinking in scenes](https://transom.org/2022/thinking-in-scenes/) ·
[Transom: story question](https://transom.org/2018/question-start-story/).

| Task | Initial model policy | Reason |
| --- | --- | --- |
| Whole episode writer and substantive rewrite | **`gpt-6-astra`**, reasoning `medium`; `high` for difficult evidence synthesis | Strongest available OpenAI starting candidate for a long, evidence-constrained narrative with distinct voices. |
| Quality challenger | **`gpt-6-sol`** or **`gpt-5.6-sol`** under the identical brief | Determine whether a less expensive strong model produces equally believable dialogue for *this* show. |
| Mechanical parsing, claim-ID extraction and formatting | Deterministic Python; optionally a model for proposals only | Never let a cheap model change approved narration. |

The production writer must have an explicit premium allowlist; `gpt-4o-mini`,
`gpt-5.6-luna`, `gpt-6-luna`, and other economy models cannot silently become
the podcast's narrative writer through environment defaults or provider
fallbacks. If Astra is unavailable to this account, require an explicit
operator selection of a strong alternative; do not silently downgrade. Pin
the requested model ID, actual returned model, prompt revision, reasoning
effort, source packet hash and draft hash in each artifact. The existing
`writer.py` and `produce.py` both currently default to `gpt-4o-mini`; the
podcast implementation must **override these defaults or use a separate writer**.

OpenAI describes Astra as its highest-capability model, and documents
`gpt-6-astra` with structured output and web-search support. Its published
claims about structured writing are relevant but are **not a direct evaluation
of believable investigative podcast dialogue**. GPT-5.6 Sol and GPT-6 Sol are
viable comparison models. As of this spec, there is no cited public benchmark
that tests these models on this exact task; a generic fiction-writing
leaderboard should not decide this show's writer.
[OpenAI model guidance](https://developers.openai.com/api/docs/guides/latest-model) ·
[Astra model details](https://developers.openai.com/api/docs/models/gpt-6-astra) ·
[GPT-5.6 Sol model](https://developers.openai.com/api/docs/models/gpt-5.6-sol).

Before making the default permanent, produce scripts for **three different
reviewed cases** (for example, a settled allegation, a court finding, and a
scientific uncertainty) with Astra and one challenger using identical evidence
packets. Hide the model IDs, then have readers score each complete script on:
first-minute pull, credible spoken dialogue, distinction among speakers,
scientific/legal accuracy, and listener payoff. Reject any script that invents
an event or asserts unsupported wrongdoing regardless of its entertainment
score. Count factual corrections and editorial minutes, not just token cost.
After voicing pilots, use episode retention and completion to revisit the
choice; a blind script preference alone cannot predict audience engagement.

For scale, OpenAI's standard short-context rates currently list Astra at
**$10 per million input tokens and $50 per million output tokens** and GPT-6
Sol at **$2/$10**. A hypothetical 8,000-input/3,000-output-token generation
is about **$0.23** with Astra or **$0.046** with Sol before reasoning-token
overhead, searches, rewrites, caching, and tax. The quality comparison is
inexpensive relative to recorded voice and editing; check actual billed usage
per request. [OpenAI API pricing](https://developers.openai.com/api/docs/pricing).

### Runtime and audio story structure

**Target 20 minutes** for the flagship two-voice episode, approximately
2,400–3,100 spoken words depending on measured delivery. Allow 12–15 minutes
when the case is narrow and 25–30 minutes when multiple documents or a real
participating author make the additional time worthwhile. Cut repetitive
synthetic banter before lengthening a script to hit a target. A 6–10 minute
version can be a standalone briefing or summary; it should not be the default
substitute for a developed author discussion.

The evidence supports testing this range, **not claiming that 20 minutes is
proven optimal for men 35–49**. Triton's U.S. podcast listener survey finds
35–54-year-olds well represented among established listeners and reports that
most monthly listeners use both audio and video. A 2025 survey of 311 podcast
professionals found a 36.7-minute median episode, but its voluntary sample and
self-reported downloads cannot establish a causal length advantage. Spotify's
genre data explicitly caution that shorter episodes do not invariably achieve
better completion. [Triton 2025 U.S. podcast report](https://info.tritondigital.com/hubfs/U.S.%20Podcast%20Report%202025/U.S.%20Podcast%20Report%202025.pdf) ·
[Podcast Marketing Trends 2025](https://podcastmarketingacademy.com/podcast-marketing-trends-report-2025/) ·
[Spotify genre study](https://creators.spotify.com/resources/podcast-fan-study).

Suggested six-act arc for a **20-minute** pilot (timings are testable editorial
targets; the final spoken script controls runtime):

| Time | Act | Listener payoff |
| --- | --- | --- |
| 0:00–0:30 | Hook | A documented surprise, a personal stake, and the episode's exact question. No long theme or biography. |
| 0:30–2:00 | Scene | Who did what, when, and why it matters; identify the rotating author and source. Give the first concrete fact before a lengthy preamble. |
| 2:00–5:00 | Source's case | Author voice explains the anchor work's central claim, method, and strongest piece of evidence. |
| 5:00–10:00 | Investigation | Follow the event sequence and original documents; Satoshi tests implications in conversation. |
| 10:00–15:00 | Competing account | A plausible alternative, contradictory document, or design limitation changes what a listener thinks is proven. |
| 15:00–20:00 | Payoff and limits | Answer the opening question as far as the record permits, identify unresolved evidence, and end with a short memorable consequence or next test. |

Treat each act change as an earned development, not a mechanical cliffhanger.
The source author can disagree with the host; the publication need not prove a
scheme. Spotify illustrates a sharp opening drop-off with a roughly one-minute
intro that improved when shortened, and suggests comparing length among
otherwise similar episodes. Transom recommends advancing an audio story through
events while inserting context as needed. [Spotify retention example](https://creators.spotify.com/resources/grow/understanding-your-episode-performance) ·
[Transom on narrative sequence](https://transom.org/2024/structure-interviews-like-a-good-story/).

Audio storytelling guidance from Transom favors a sequence of events with
context inserted when it clarifies the story. Spotify's creator guidance says
to inspect early drop-offs and compare episodes with similar themes and length
before attributing engagement to an edit. These are editorial patterns to
test, not promises of virality. [Transom: structure interviews](https://transom.org/2024/structure-interviews-like-a-good-story/)
and [Spotify: episode performance](https://creators.spotify.com/resources/grow/understanding-your-episode-performance).

## Contracts and workflow

```mermaid
flowchart TB
    A["Reviewed case and evidence stack"] --> B["Complete master script"]
    B --> C["Editorial and medical review"]
    C --> D["Deterministic speaker turns"]
    D --> E["Runway speech jobs"]
    D --> F["Human-recorded replacement turns"]
    E --> G["Audio assembly and listening review"]
    F --> G
    G --> H["Private episode and short clips"]
```

Proposed commands and files (these commands **do not exist yet**):

| Stage | Input → artifact | Hard requirement |
| --- | --- | --- |
| `podcast write` | Reviewed case + `source_author.json` + `evidence_packet.json` + versioned `podcast_writer_prompt.md` → beat map, `master-script.md`, `claims.json` | Source-bearing moments are woven into natural dialogue; every factual passage carries claim IDs and source locators; reviewer can see the complete episode before any voice charge. |
| `podcast approve` | Edited script → signed `approved-script.json` | Review content, rotating author attribution, portrayal mode, disclosure, sponsor copy, context, and medical claims. Store a content hash and reviewer. |
| `podcast parse` | Approved script → `turns.json` | No content rewriting; turn order, speaker, exact text, claim IDs and punctuation preserved. |
| `podcast voices --dry-run` | Turns + private voice map → jobs and cost estimate | Validate access, limits, selected voices and available credits. |
| `podcast voices --live` | Approved turns → durable task ledger + WAV/MP3 per turn or scene | Bounded concurrency, job cap, retries only after provider reconciliation; reuse unchanged audio by text/voice/model hash. |
| `podcast assemble` | Audio + script order → private master, transcript, chapters | Normalize levels, breaths and pauses by listening; preserve deliberate overlap; reject missing/incorrect turns. |
| `podcast qa` | Private master → approval record | Listen end to end; check factual wording, names, pronunciation, voice continuity, ads and music licenses. |
| `podcast clips` | Approved master → short audio/video candidates | Transcript timestamps identify moments; an editor selects clips whose hooks faithfully represent the full episode. |

Example intermediate turn (the structure, not a claim that these words were
approved):

```json
{
  "act": "evidence",
  "turn_id": "evidence-07",
  "speaker_id": "source_author",
  "text": "The published finding concerns the litigation. It does not answer every question about prescriptions.",
  "claim_ids": ["C-LITIGATION-01"],
  "delivery": "matter-of-fact",
  "script_revision": "SHA256_OF_APPROVED_MASTER"
}
```

The case packet and speaker registry live under version control when public.
Reviewed source excerpts, approval signatures, voice IDs, full scripts, paid-job
ledgers and generated audio live in the existing **private episode storage**.
Save a text-only release record with source URLs, claim IDs, version hashes,
runtime, license references and publication identifiers. Treat the story and
media branches as independent jobs keyed to the same case revision so neither
must wait for the other's renders.

The writer's claim ledger must mark **finding**, **allegation**, **inference**,
and **unanswered question** separately. It must also retain the actor, action,
date and source for any suggested coordination or concealment. A proven scheme
may be described plainly; an unproven one can be examined as a hypothesis only
when the episode identifies the observable evidence that would distinguish it
from other explanations. This gives Satoshi room to pursue a difficult question
without turning uncertainty into a theatrical accusation.

## Voice engine: what Runway actually supplies

Runway Dev currently lists `eleven_multilingual_v2` and `eleven_v3` as
text-to-audio models. Its published pricing is **one credit per 50 input
characters** for each, with a one-credit minimum for `eleven_v3`; developer
credits are listed at $0.01 each. A roughly 16,000-character 20-minute script
therefore starts around 320 credits, or **$3.20 for one generation pass**,
before character
minimums, alternate takes, music, processing or other provider charges. This
is a planning estimate, not a quoted production price.
[Runway models](https://docs.dev.runwayml.com/guides/models/) ·
[Runway pricing](https://docs.dev.runwayml.com/guides/pricing/).

The existing `runway_media.py` uses Runway's `eleven_multilingual_v2` API for
single-voice short-form beats. For a podcast, start with **scene-sized or
turn-sized Runway speech jobs per assigned voice**, fetch the audio and assemble
locally with FFmpeg. Speech jobs across speakers may run concurrently; the
ordered script remains the source of truth. Review cadence and pauses by ear:
mechanically inserting the same pause after every line makes a conversation
sound like three machines waiting their turn. Generate two or more candidate
takes for selected pivotal scenes, not the entire episode by default.

Important distinction: ElevenLabs documents a separate **Text to Dialogue**
API on Eleven v3 that accepts multiple voice-tagged turns in a chunk and
recommends at most about **2,000 characters per request** for reliability.
It is **not established** that Runway exposes that same multi-speaker dialogue
endpoint merely because Runway lists `eleven_v3` for audio generation. The
architecture should support a replaceable direct ElevenLabs dialogue adapter
only if its separate API access and commercial terms are configured; otherwise
use the verified Runway single-speaker path. [ElevenLabs Text to Dialogue](https://elevenlabs.io/docs/overview/capabilities/text-to-dialogue).

## Engagement and measurement

Open each pilot with an actual case question, bring a specific document or
finding into the dialogue early, and use the rotating source perspective to clarify and challenge an
easy inference. Short promotional clips should keep the episode's conclusion
intact. Spotify describes hooks and story arcs for promotional clips but does
not supply a universal winning clip length. [Spotify clip examples](https://creators.spotify.com/resources/grow/spotify-clips-drive-discovery).

Track starts, retention at 30 seconds, 2 minutes and each act boundary,
**listened minutes per start**, average consumption percentage, completion,
follows per listener and clip-to-episode visits. The primary pilot objective is
listened minutes *and* follow rate without a first-minute collapse; percentage
completion alone rewards shorter versions by construction. Compare an
18–22-minute cut with a 12–15-minute edit of the **same case**; then test a
25–30-minute variant only if the document trail supports it. Match release
age and source traffic as closely as possible, and note that uploading two
cuts to public feeds introduces audience-selection and platform effects.
Spotify offers episode audience-retention analytics; Apple reports average
consumption from aggregated listening data. The choice of cast should be
revisited after actual audience behavior, not assumed from genre intuition.
[Spotify retention](https://creators.spotify.com/resources/grow/understanding-your-episode-performance) ·
[Apple Podcasts analytics](https://podcasters.apple.com/support/5392-listener-analytics).

## Acceptance criteria

1. A reviewed case with a **verified named author or patent inventor** generates
   one complete readable master script and a claim-to-line trace. Its evidence
   packet includes distinct original works, a competing or limiting account,
   source locators, and a documented reason for the chosen source count.
   Missing or uncertain authorship blocks paid generation.
2. Parsing approved text preserves every spoken word and yields only registered
   speaker IDs; each factual assertion, including one inside an aside, has
   reviewed source support. Listeners hear concrete source attributions across
   the story without a fixed citation cadence; show notes link the full works.
   The writer records its showrunner prompt version and hash alongside the
   evidence and script revision so a reviewer can reproduce the brief.
3. Dry-run gives a voice and cost plan without provider charges. Repeated live
   submission does not double-charge after ambiguous timeouts.
4. Audio assets can be regenerated for one changed turn without regenerating
   the whole episode; old audio cannot silently occupy a revised turn.
5. The private MP3/WAV passes an end-to-end listening review; transcript,
   chapters and clip provenance point to the same approved script revision.
6. No feed or social platform receives an episode until a distinct publication
   approval. A synthetic author portrayal is identified in audio and metadata,
   and is never presented as a real interview or endorsement.
