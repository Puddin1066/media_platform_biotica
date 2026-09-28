"""Persist generated media to Cloudflare R2 before production continues."""
import hashlib
import mimetypes
import os
from pathlib import Path


def _sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


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
    base = os.environ["MEDIA_PUBLIC_BASE_URL"].rstrip("/")
    return {
        "bucket": bucket,
        "key": key,
        "url": f"{base}/{key}",
        "sha256": checksum,
        "bytes": path.stat().st_size,
    }


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
