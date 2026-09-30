"""Persist generated media to Cloudflare R2 before production continues."""
import hashlib
import mimetypes
import os
import urllib.parse
from pathlib import Path


def _sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def public_base_url():
    """Return the HTTPS base Meta/browsers can fetch without credentials.

    MEDIA_PUBLIC_BASE_URL must be a public custom domain or r2.dev URL.
    The account S3 API host (*.r2.cloudflarestorage.com) requires auth and
    makes Instagram Graph hang until the container poll times out.
    """
    raw = (os.environ.get("MEDIA_PUBLIC_BASE_URL") or "").strip()
    if not raw:
        raise ValueError("MEDIA_PUBLIC_BASE_URL is required")
    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("MEDIA_PUBLIC_BASE_URL must be an https:// base URL")
    host = parsed.hostname or ""
    if host.endswith(".r2.cloudflarestorage.com") or host == "r2.cloudflarestorage.com":
        raise ValueError(
            "MEDIA_PUBLIC_BASE_URL must not be the R2 S3 API host "
            "(*." + "r2.cloudflarestorage.com). Use a public r2.dev URL or "
            "custom domain so Instagram can download the Reel without credentials."
        )
    return raw.rstrip("/")


def _client(client=None):
    if client is not None:
        return client
    import boto3
    return boto3.client(
        "s3",
        endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )


def _key(value):
    key = str(value).lstrip("/")
    if not key or ".." in Path(key).parts:
        raise ValueError("Invalid media object key")
    return key


def persist(path, key, client=None):
    path = Path(path)
    if not path.is_file() or path.stat().st_size <= 0:
        raise ValueError("Durable media upload requires a non-empty file")
    key = _key(key)
    client = _client(client)
    bucket = os.environ["R2_BUCKET"]
    checksum = _sha256(path)
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    client.upload_file(
        str(path), bucket, key,
        ExtraArgs={"ContentType": content_type, "Metadata": {"sha256": checksum}},
    )
    head = client.head_object(Bucket=bucket, Key=key)
    if int(head.get("ContentLength", -1)) != path.stat().st_size:
        raise RuntimeError("R2 verification failed: size mismatch")
    if (head.get("Metadata") or {}).get("sha256") != checksum:
        raise RuntimeError("R2 verification failed: checksum metadata mismatch")
    base = public_base_url()
    return {
        "bucket": bucket,
        "key": key,
        "url": f"{base}/{key}",
        "sha256": checksum,
        "bytes": path.stat().st_size,
    }


PLATE_PREFIX = "satoshi/plates/"
PLATE_SUFFIXES = {".mp4", ".mov", ".m4v", ".webm"}


def _r2_configured():
    return all(os.environ.get(name) for name in (
        "R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"))


def available_plates(prefix=PLATE_PREFIX, client=None, bucket=None):
    """List reusable host videos already stored under the plate prefix.

    Empty folder markers are ignored. Missing R2 configuration returns no plates
    so callers can fall back to an explicit key or a clear error.
    """
    bucket = bucket or os.environ.get("R2_BUCKET")
    if client is None:
        if not _r2_configured():
            return []
        client = _client()
    if not bucket:
        return []
    plates = []
    token = None
    while True:
        kwargs = {"Bucket": bucket, "Prefix": prefix}
        if token:
            kwargs["ContinuationToken"] = token
        page = client.list_objects_v2(**kwargs)
        for item in page.get("Contents") or []:
            key = str(item.get("Key") or "")
            size = int(item.get("Size") or 0)
            if not key.startswith(prefix) or key.endswith("/") or size <= 0:
                continue
            if Path(key).suffix.lower() not in PLATE_SUFFIXES:
                continue
            modified = item.get("LastModified")
            plates.append({
                "key": key,
                "bytes": size,
                "last_modified": modified.isoformat() if hasattr(modified, "isoformat") else str(modified or ""),
            })
        if not page.get("IsTruncated"):
            break
        token = page.get("NextContinuationToken")
        if not token:
            break
    plates.sort(key=lambda item: item["key"])
    return plates


def select_plate(plates, seed):
    """Pick one available plate. The same seed always selects the same object."""
    ordered = sorted(plates, key=lambda item: item["key"])
    if not ordered:
        raise ValueError(
            "No plates available under satoshi/plates/; upload a plate or set SATOSHI_MASTER_HOST_R2_KEY"
        )
    digest = hashlib.sha256(str(seed).encode()).hexdigest()
    return ordered[int(digest, 16) % len(ordered)]


def resolve_plate(seed, explicit_key=None):
    """Choose the host plate for an episode.

    An explicit key or repository plate variable wins. Otherwise one video
    already stored under satoshi/plates/ is reused. Nothing new is uploaded.
    """
    key = str(
        explicit_key
        or os.environ.get("SATOSHI_MASTER_HOST_R2_KEY")
        or os.environ.get("SATOSHI_DEFAULT_PLATE_R2_KEY")
        or os.environ.get("SATOSHI_PLATE_R2_KEY")
        or ""
    ).strip()
    if key:
        return {"key": key, "source": "explicit"}
    chosen = select_plate(available_plates(), seed)
    return {"key": chosen["key"], "source": "available", "bytes": chosen.get("bytes")}


def fetch(key, destination, client=None):
    """Download a private R2 object and verify size/checksum metadata when present."""
    key = _key(key)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    client = _client(client)
    bucket = os.environ["R2_BUCKET"]
    head = client.head_object(Bucket=bucket, Key=key)
    expected_size = int(head.get("ContentLength", -1))
    expected_sha = (head.get("Metadata") or {}).get("sha256")
    part = destination.with_suffix(destination.suffix + ".part")
    part.unlink(missing_ok=True)
    try:
        client.download_file(bucket, key, str(part))
        if not part.is_file() or part.stat().st_size <= 0:
            raise RuntimeError("R2 download produced an empty file")
        if expected_size >= 0 and part.stat().st_size != expected_size:
            raise RuntimeError("R2 download verification failed: size mismatch")
        checksum = _sha256(part)
        if expected_sha and checksum != expected_sha:
            raise RuntimeError("R2 download verification failed: checksum mismatch")
        part.replace(destination)
    finally:
        part.unlink(missing_ok=True)
    return {
        "bucket": bucket,
        "key": key,
        "sha256": _sha256(destination),
        "bytes": destination.stat().st_size,
        "path": str(destination),
    }
