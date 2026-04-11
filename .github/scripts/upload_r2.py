#!/usr/bin/env python3

from __future__ import annotations

import mimetypes
import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

import boto3
from botocore.config import Config


MIME_TYPES = {
    ".js": "application/javascript",
    ".mjs": "application/javascript",
    ".cjs": "application/javascript",
    ".css": "text/css",
    ".html": "text/html",
    ".json": "application/json",
    ".xml": "application/xml",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".avif": "image/avif",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".otf": "font/otf",
    ".eot": "application/vnd.ms-fontobject",
    ".txt": "text/plain",
    ".map": "application/json",
    ".webp": "image/webp",
}


def get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def detect_content_type(path: Path) -> str:
    return MIME_TYPES.get(path.suffix.lower()) or mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def collect_uploads(directory: Path, key_prefix: str) -> list[tuple[str, Path]]:
    if not directory.exists():
        return []

    uploads: list[tuple[str, Path]] = []
    for file_path in sorted(path for path in directory.rglob("*") if path.is_file()):
        relative_path = file_path.relative_to(directory).as_posix()
        uploads.append((f"{key_prefix}/{relative_path}", file_path))
    return uploads


def build_client():
    return boto3.client(
        "s3",
        endpoint_url=get_required_env("R2_CDN_S3_URL"),
        aws_access_key_id=get_required_env("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=get_required_env("R2_SECRET_ACCESS_KEY"),
        region_name="auto",
        config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
    )


def upload_file(client, bucket: str, key: str, file_path: Path, *, verbose: bool = False) -> str:
    content_type = detect_content_type(file_path)
    presigned_url = client.generate_presigned_url(
        ClientMethod="put_object",
        Params={"Bucket": bucket, "Key": key, "ContentType": content_type},
        ExpiresIn=900,
        HttpMethod="PUT",
    )

    if verbose:
        parsed = urlparse(presigned_url)
        print(f"  PUT {parsed.scheme}://{parsed.netloc}{parsed.path}")

    with file_path.open("rb") as file_handle:
        request = urllib.request.Request(
            presigned_url,
            data=file_handle.read(),
            method="PUT",
            headers={"Content-Type": content_type},
        )
        with urllib.request.urlopen(request) as response:
            if response.status not in (200, 201):
                raise RuntimeError(f"Unexpected upload status {response.status}")

    return key


def main() -> int:
    bucket = get_required_env("R2_BUCKET")
    max_workers = int(os.getenv("R2_UPLOAD_WORKERS", "20"))
    verbose = os.getenv("R2_VERBOSE", "").lower() in ("1", "true", "yes")

    uploads = collect_uploads(Path("assets"), "assets")

    if not uploads:
        print("No files found to upload.")
        return 0

    print(f"Uploading {len(uploads)} files to R2 bucket {bucket}...")

    client = build_client()
    failures: list[str] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(upload_file, client, bucket, key, file_path, verbose=verbose): key
            for key, file_path in uploads
        }

        for index, future in enumerate(as_completed(futures), start=1):
            key = futures[future]
            try:
                future.result()
            except Exception as error:  # noqa: BLE001
                failures.append(f"{key}: {type(error).__name__}: {error}")

            if index % 50 == 0 or index == len(uploads):
                print(f"  {index}/{len(uploads)} processed")

    if failures:
        print("R2 upload failed for the following objects:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    print("R2 upload completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
