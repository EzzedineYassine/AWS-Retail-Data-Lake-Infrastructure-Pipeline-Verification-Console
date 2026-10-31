from pathlib import Path
from typing import Any, Dict, Optional, Protocol


class DataLakeStorageBackend(Protocol):
    def get_text_object(self, bucket: str, key: str) -> str: ...

    def put_text_object(
        self,
        bucket: str,
        key: str,
        body: str,
        content_type: str = "text/csv",
        metadata: Optional[Dict[str, str]] = None,
    ) -> None: ...


class S3StorageBackend:
    def __init__(self, s3_client: Optional[Any] = None) -> None:
        if s3_client is None:
            import boto3

            self._client = boto3.client("s3")
        else:
            self._client = s3_client

    def get_text_object(self, bucket: str, key: str) -> str:
        response = self._client.get_object(Bucket=bucket, Key=key)
        raw_bytes = response["Body"].read()
        return raw_bytes.decode("utf-8")

    def put_text_object(
        self,
        bucket: str,
        key: str,
        body: str,
        content_type: str = "text/csv",
        metadata: Optional[Dict[str, str]] = None,
    ) -> None:
        put_kwargs: Dict[str, Any] = {
            "Bucket": bucket,
            "Key": key,
            "Body": body.encode("utf-8"),
            "ContentType": content_type,
            "ServerSideEncryption": "AES256",
        }
        if metadata:
            put_kwargs["Metadata"] = metadata
        self._client.put_object(**put_kwargs)


class LocalFilesystemS3Backend:
    def __init__(self, root_directory: Path) -> None:
        self.root_directory = Path(root_directory)
        self.root_directory.mkdir(parents=True, exist_ok=True)
        self.object_metadata: Dict[str, Dict[str, str]] = {}

    def _resolve_path(self, bucket: str, key: str) -> Path:
        normalized_key = key.lstrip("/").replace("/", "\\")
        return self.root_directory / bucket / normalized_key

    def get_text_object(self, bucket: str, key: str) -> str:
        target_path = self._resolve_path(bucket, key)
        if not target_path.exists():
            raise FileNotFoundError(f"Object s3://{bucket}/{key} does not exist")
        return target_path.read_text(encoding="utf-8")

    def put_text_object(
        self,
        bucket: str,
        key: str,
        body: str,
        content_type: str = "text/csv",
        metadata: Optional[Dict[str, str]] = None,
    ) -> None:
        target_path = self._resolve_path(bucket, key)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(body, encoding="utf-8", newline="\n")
        self.object_metadata[f"{bucket}/{key}"] = {
            "content_type": content_type,
            **(metadata or {}),
        }
