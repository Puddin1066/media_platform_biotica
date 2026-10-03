# Runway operations available to Satoshi Studio

Source: [Runway official OpenAPI specification](https://github.com/runwayml/openapi/blob/main/openapi.json).

Snapshot checksum: `ef7e1923afafd394c0cd3f76b7c0adf8edb9d29d715de5c907022482d737336a`. 65 method/path operations across 49 paths.

Studio exposes every operation through **Runway tools**. Required fields and model-specific request schemas are available in the panel. Generation, provider state changes, and enterprise-only access are identified separately. An operation being callable does not mean this account has permission or that its media output has passed review.

## Satoshi production controls

| Detail | Preferred operation or component |
| --- | --- |
| Narration and voice delivery | Saved voice module; optionally `POST /v1/text_to_speech` |
| Speaking performance | `POST /v1/avatar_videos` |
| Face animation on a moving plate | `POST /v1/character_performance` |
| Reusable setting change | `POST /v1/video_to_video` with Aleph |
| New plate or illustrative motion | `POST /v1/image_to_video` or `/v1/text_to_video` |
| Illustrations | `POST /v1/text_to_image` |
| Sound cues | `POST /v1/sound_effect` |
| Framing, loop phase, evidence layout, captions, music mix | FFmpeg and Remotion |
| Provider status, failures and credits | `GET /v1/tasks/{id}`, `GET /v1/organization` |

The production script is not a visual-generation prompt. Act Two takes a character and reference performance. Aleph takes a scene-edit prompt. These controls stay independent.

## Complete operation inventory

### Characters and voices

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/v1/avatars` | List avatars |
| POST | `/v1/avatars` | Create avatar |
| GET | `/v1/avatar_conversations` | List conversations |
| GET | `/v1/avatar_usage` | Get avatar usage |
| GET | `/v1/avatar_conversations/{id}` | Get conversation |
| DELETE | `/v1/avatar_conversations/{id}` | Delete conversation |
| GET | `/v1/avatars/{id}` | Get avatar |
| PATCH | `/v1/avatars/{id}` | Update avatar |
| DELETE | `/v1/avatars/{id}` | Delete avatar |
| POST | `/v1/avatar_videos` | Generate avatar video from audio or text |
| POST | `/v1/documents` | Create document |
| GET | `/v1/documents` | List documents |
| GET | `/v1/documents/{id}` | Get document |
| PATCH | `/v1/documents/{id}` | Update document |
| DELETE | `/v1/documents/{id}` | Delete document |
| POST | `/v1/realtime_sessions` | Create realtime session |
| GET | `/v1/realtime_sessions/{id}` | Get realtime session |
| DELETE | `/v1/realtime_sessions/{id}` | Cancel realtime session |
| GET | `/v1/voices` | List voices |
| POST | `/v1/voices` | Create a voice |
| GET | `/v1/voices/{id}` | Get a voice |
| PATCH | `/v1/voices/{id}` | Update a voice |
| DELETE | `/v1/voices/{id}` | Delete a voice |
| POST | `/v1/voices/preview` | Preview a voice |

### Account and task tools

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/v1/tasks/{id}` | Get task detail |
| DELETE | `/v1/tasks/{id}` | Cancel or delete a task |
| GET | `/v1/organization/webapp/usage` | List linked workspace usage |
| GET | `/v1/organization/webapp/audit_logs` | List linked workspace audit logs |
| GET | `/v1/organization/webapp/audit_logs/{eventId}` | Get a linked workspace audit log entry |
| GET | `/v1/organization` | Get organization information |
| POST | `/v1/organization/usage` | Query credit usage |
| POST | `/v1/uploads` | Upload a file |

### Image and video

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/v1/image_to_video` | Image to video |
| POST | `/v1/text_to_video` | Text to video |
| POST | `/v1/video_to_video` | Video to video |
| POST | `/v1/text_to_image` | Text/Image to Image |
| POST | `/v1/character_performance` | Control a character |

### Enhancement

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/v1/image_upscale` | Image upscale |
| POST | `/v1/video_upscale` | Video upscale |
| POST | `/v1/video_to_hdr` | Video to HDR |

### Audio

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/v1/sound_effect` | Generate sound effects |
| POST | `/v1/speech_to_speech` | Speech to speech |
| POST | `/v1/text_to_speech` | Text to speech |
| POST | `/v1/voice_dubbing` | Voice dubbing |
| POST | `/v1/voice_isolation` | Voice isolation |

### Model routing

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/v1/generate/video` | Routed video generation |
| POST | `/v1/generate/image` | Routed image generation |
| POST | `/v1/generate/audio` | Routed audio generation |
| GET | `/v1/routers` | List Model Routers |
| POST | `/v1/routers` | Create Model Router |
| GET | `/v1/routers/{id}` | Retrieve Model Router |
| PATCH | `/v1/routers/{id}` | Update Model Router |
| DELETE | `/v1/routers/{id}` | Delete Model Router |
| GET | `/v1/routers/{id}/requests` | List Model Router requests |

### Recipes

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/v1/recipes/ad_localization` | Localize an ad image |
| POST | `/v1/recipes/marketing_stock_image` | Create a marketing stock image |
| POST | `/v1/recipes/product_ad` | Create a product ad video |
| POST | `/v1/recipes/product_campaign_image` | Create product campaign images |
| POST | `/v1/recipes/product_swap` | Swap a product in a reference video |
| POST | `/v1/recipes/multi_shot_video` | Create a multi-shot video |
| POST | `/v1/recipes/product_ugc` | Create a product UGC video |

### Published workflows

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/v1/workflows/{id}` | Run a published workflow |
| GET | `/v1/workflows/{id}` | Get workflow details |
| GET | `/v1/workflows` | List published workflows |
| GET | `/v1/workflow_invocations/{id}` | Get workflow invocation detail |

## Execution and reuse

The operation worker validates inputs before provider submission, checks the API balance against the entered estimate, and checkpoints a reservation before mutations. It never blindly resubmits an ambiguous paid request. Terminal provider failure details are preserved. Task and published-workflow media are copied into R2 and displayed as reusable links in Studio. Each request/result pair is saved under `studio/runway_jobs/<request_id>/` independently of episode modules.

A returned upload form still requires transferring file bytes. Its temporary signed fields are retained only in the Actions diagnostic artifact. Realtime sessions require a separate client/session connection. CRUD endpoints manage provider resources; they are not automatically part of each episode. Published workflow inputs must match that workflow’s configured node IDs.

All catalog operations are schema-supported. Only avatar video generation has a successfully collected live output in this episode; Act Two generation has failed. Other operations remain individually unverified. No bulk paid access test is performed.

Refresh after reviewing Runway changes: `python scripts/sync_runway_catalog.py --source /path/to/official/openapi.json`.
