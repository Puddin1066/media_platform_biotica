# Biotica Media studio architecture

Biotica Media is organized as a production studio, not a set of disconnected generators.
The canonical unit of work is one **studio episode object** created from an authoritative topic.

```text
TOPIC
  -> audience/sponsor classification
  -> RESEARCH PACKET
  -> SCRIPT
  -> VISUAL PLAN
  -> ASSETS
  -> RENDER
  -> REVIEW
  -> PUBLISH PACKAGE
  -> ANALYTICS
```

`studio_episode.py` is the coordination contract. Existing specialist tools remain responsible for their own validation and outputs; the studio object records where those outputs belong and what stage is complete.

## Topic authority

A topic supplied by the user or an explicit upstream request is authoritative. Classification may add pillar, audience job, sponsor fit, or special editorial rules, but it must not replace or rebalance the topic. The episode ID is derived from the supplied topic so silent topic substitution invalidates the object.

Autonomous topic discovery is not part of the default production path. If a separate discovery workflow is added later, it must output a proposed topic first; production begins only from the selected topic.

## Canonical stages

| Stage | Typical artifact | Existing producer |
| --- | --- | --- |
| `topic` | authoritative topic + episode ID | `studio_episode.new_episode` |
| `research` | evidence/research bundle, source receipts | `web_research.py`, `research.py`, case workflow |
| `script` | reviewed short script/storyboard or long-form script | `produce.py`, `web_handoff.py`, podcast agents |
| `visual_plan` | shot/graphics/visual direction | `visual_director.py`, `pipeline.py` |
| `assets` | host plate, audio, approved clips, generated illustrations | `episode.py`, Runway adapters, creator media |
| `render` | private MP4/audio/document preview | Remotion / render adapters |
| `review` | factual, rights, visual, timing, medical and editorial approval | human/editorial gate |
| `publish_package` | approved captions, description, media URL, release manifest | platform/export adapters |
| `analytics` | retention, completion, shares, saves, follows, sponsor signals | Instagram/experiment analytics |

Stages are monotonic. A later stage cannot be attached while an earlier required stage is missing. A material editorial revision should create a new revision rather than silently rewinding a published object.

## Why this matters

The object provides one durable identity across every derivative format. A single evidence packet can support a Reel, YouTube Short, podcast segment, newsletter, sponsor brief, or long-form investigation while preserving the same topic and provenance. Formats can differ in pacing and creative treatment without losing the underlying editorial record.

The studio object is coordination metadata, not evidence. Attaching a research artifact does not verify its claims; attaching media does not confer rights; attaching a render does not approve publication. Existing quality gates remain authoritative.

## Commercial layer

Sponsor metadata is attached as classification, not as an editorial instruction. It can answer questions such as which sponsor categories naturally fit an episode and which audience need it serves. It cannot change a scientific conclusion, suppress contrary evidence, or replace the user-selected topic.

The studio should optimize over time for audience accrual and sponsor value using observed performance: first-seconds hold, completion, shares, saves, follows per thousand views, return viewers, and qualified sponsor interest. Those measurements feed future creative decisions; they do not rewrite prior evidence.
