"""S3 adapter: file storage for uploads and backups.

Rule 1: the ONLY file that talks to Amazon S3. Bucket names and region come from
settings (S3_BUCKET_UPLOADS, AWS_REGION). Uploads go browser -> S3 directly using a
short-lived pre-signed link (docs/ARCHITECTURE.md "Uploads").

Hard delete (CLAUDE.md s.6) starts here: `delete` must really remove the object.

Only the interface and a Fake live here; no real network calls.
"""

from __future__ import annotations

from typing import Protocol


class ObjectStore(Protocol):
    async def presign_upload(self, key: str, expires_seconds: int = 300) -> str: ...
    async def put(self, key: str, data: bytes) -> None: ...
    async def get(self, key: str) -> bytes: ...
    async def delete(self, key: str) -> None: ...
    async def exists(self, key: str) -> bool: ...


class FakeObjectStore:
    def __init__(self, bucket: str = "fake-uploads") -> None:
        self.bucket = bucket
        self.objects: dict[str, bytes] = {}

    async def presign_upload(self, key: str, expires_seconds: int = 300) -> str:
        return f"https://fake-s3.invalid/{self.bucket}/{key}?expires={expires_seconds}"

    async def put(self, key: str, data: bytes) -> None:
        self.objects[key] = data

    async def get(self, key: str) -> bytes:
        return self.objects[key]

    async def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    async def exists(self, key: str) -> bool:
        return key in self.objects
