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


def persist(path, key, client=None):
    path = Path(path)
    if not path.is_file() or path.stat().st_size <= 0:
        raise ValueError("Durable media upload requires a non-empty file")
    key = str(key).lstrip("/")
    if not key or ".." in Path(key).parts:
        raise ValueError("Invalid media object key")
    if client is None:
        import boto3
        client = boto3.client(
            "s3",
            endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
            region_name="auto",
        )
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
