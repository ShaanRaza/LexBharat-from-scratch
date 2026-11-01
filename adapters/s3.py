"""Amazon S3 for uploads. The ONLY file that talks to S3.

Private bucket, KMS encryption, no public links, expiring pre-signed URLs only.
Object keys always start with the user id, so one user's key can never be another's.
"""

from __future__ import annotations

from typing import Protocol

from core.settings import Settings

EXPIRY_SECONDS = 900


class FileStore(Protocol):
    async def presign_upload(self, user_id: str, document_id: str) -> str: ...
    async def presign_download(self, user_id: str, document_id: str) -> str: ...
    async def read(self, user_id: str, document_id: str) -> bytes: ...
    async def delete(self, user_id: str, document_id: str) -> None: ...
    async def exists(self, user_id: str, document_id: str) -> bool: ...


def object_key(user_id: str, document_id: str) -> str:
    if not user_id or not document_id or "/" in user_id + document_id:
        raise ValueError("bad id")
    return f"uploads/{user_id}/{document_id}"


class S3Store:
    """Real (boto3, lazy). Not verified against AWS."""

    def __init__(self, settings: Settings):
        self._s = settings
        self._c = None

    def _client(self):
        if self._c is None:
            import boto3

            self._c = boto3.client("s3", region_name=self._s.AWS_REGION)
        return self._c

    def _put_args(self, key: str) -> dict:
        return {
            "Bucket": self._s.S3_BUCKET_UPLOADS,
            "Key": key,
            "ServerSideEncryption": "aws:kms",
            "SSEKMSKeyId": self._s.S3_KMS_KEY_ID,
        }

    async def presign_upload(self, user_id, document_id):
        return self._client().generate_presigned_url(
            "put_object",
            Params=self._put_args(object_key(user_id, document_id)),
            ExpiresIn=EXPIRY_SECONDS,
        )

    async def presign_download(self, user_id, document_id):
        return self._client().generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self._s.S3_BUCKET_UPLOADS,
                "Key": object_key(user_id, document_id),
            },
            ExpiresIn=EXPIRY_SECONDS,
        )

    async def read(self, user_id, document_id):
        r = self._client().get_object(
            Bucket=self._s.S3_BUCKET_UPLOADS, Key=object_key(user_id, document_id)
        )
        return r["Body"].read()

    async def delete(self, user_id, document_id):
        self._client().delete_object(
            Bucket=self._s.S3_BUCKET_UPLOADS, Key=object_key(user_id, document_id)
        )

    async def exists(self, user_id, document_id):
        try:
            self._client().head_object(
                Bucket=self._s.S3_BUCKET_UPLOADS, Key=object_key(user_id, document_id)
            )
        except Exception:  # noqa: BLE001
            return False
        return True


class FakeFileStore:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    def put(self, user_id: str, document_id: str, data: bytes) -> None:
        self.files[object_key(user_id, document_id)] = data

    async def presign_upload(self, user_id, document_id):
        return (
            f"https://fake-s3/{object_key(user_id, document_id)}?exp={EXPIRY_SECONDS}"
        )

    async def presign_download(self, user_id, document_id):
        return await self.presign_upload(user_id, document_id)

    async def read(self, user_id, document_id):
        return self.files[object_key(user_id, document_id)]

    async def delete(self, user_id, document_id):
        self.files.pop(object_key(user_id, document_id), None)

    async def exists(self, user_id, document_id):
        return object_key(user_id, document_id) in self.files
