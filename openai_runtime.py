"""Shared OpenAI Responses runtime for Biotica Media.

Owns credential resolution, provider invocation, status diagnostics, output/source
extraction, and a bounded live preflight. Domain modules remain responsible for
their own scientific/editorial validation and spend ledgers.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

ENDPOINT = "https://api.openai.com/v1/responses"
MAX_RESPONSE_BYTES = 4_000_000


def credential(env=None):
    env = os.environ if env is None else env
    value = str(env.get("OPENAI_API_KEY", "")).strip()
    if not value:
        raise ValueError("OPENAI_API_KEY missing")
    return value


def require_live(env=None):
    env = os.environ if env is None else env
    if env.get("OPENAI_LIVE_ENABLED") != "true":
        raise ValueError("OPENAI_LIVE_ENABLED must be true")
    return credential(env)


def provider_status(result):
    status = result.get("status", "unknown")
    details = result.get("incomplete_details") or {}
    reason = details.get("reason") if isinstance(details, dict) else None
    error = result.get("error")
    return f"status={status}; reason={reason or 'unspecified'}; error={error or 'none'}"


def require_completed(result):
    if result.get("status") != "completed":
        raise ValueError("OpenAI response not completed: " + provider_status(result))
    return result


def call_responses(body, key=None, timeout=180, max_bytes=MAX_RESPONSE_BYTES):
    """Perform one Responses API call with bounded response size and explicit errors."""
    key = key or credential()
    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST",
    )

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=timeout) as response:
            raw = response.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise RuntimeError("OpenAI response exceeded configured byte limit")
        return json.loads(raw)
    except urllib.error.HTTPError as exc:
        body_text = exc.read(4000).decode(errors="replace")
        raise RuntimeError(f"OpenAI HTTP {exc.code}: {body_text}") from None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(f"OpenAI request failed: {type(exc).__name__}") from None


def extract_output(result):
    """Return concatenated output text plus deduplicated consulted/cited sources."""
    require_completed(result)
    texts = []
    sources = {}
    for item in result.get("output", []):
        if item.get("type") == "web_search_call":
            for source in item.get("action", {}).get("sources", []):
                url = source.get("url")
                if isinstance(url, str) and url.startswith(("https://", "http://")):
                    sources[url] = {
                        "url": url,
                        "title": source.get("title", ""),
                        "role": "consulted",
                    }
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") != "output_text":
                continue
            texts.append(content.get("text", ""))
            for note in content.get("annotations", []):
                citation = note.get("url_citation", note)
                if note.get("type") == "url_citation" and isinstance(citation.get("url"), str):
                    url = citation["url"]
                    sources[url] = {
                        "url": url,
                        "title": citation.get("title", ""),
                        "role": "cited",
                    }
    text = "".join(texts).strip()
    if not text:
        raise ValueError("OpenAI response contained no output text")
    return text, sorted(sources.values(), key=lambda source: (source["url"], source["role"]))


def extract_json(result):
    text, sources = extract_output(result)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        raise ValueError("OpenAI structured output was not valid JSON") from None
    return payload, sources


def preflight(model, key=None):
    """Cheap live contract test for auth, model, structured output, web search and sources."""
    body = {
        "model": model,
        "store": False,
        "instructions": "This is a CI provider-contract check. Follow the requested schema exactly.",
        "input": "Use web search once, then return ok=true and a short diagnostic string.",
        "tools": [{"type": "web_search"}],
        "tool_choice": "auto",
        "include": ["web_search_call.action.sources"],
        "max_tool_calls": 1,
        "max_output_tokens": 600,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "provider_preflight",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["ok", "diagnostic"],
                    "properties": {
                        "ok": {"type": "boolean"},
                        "diagnostic": {"type": "string"},
                    },
                },
            }
        },
    }
    result = call_responses(body, key=key, timeout=90)
    payload, sources = extract_json(result)
    if payload.get("ok") is not True:
        raise ValueError("OpenAI preflight returned ok=false")
    if not sources:
        raise ValueError("OpenAI preflight returned no web-search sources")
    return {
        "status": "success",
        "model": result.get("model", model),
        "source_count": len(sources),
        "provider_id": result.get("id"),
    }
