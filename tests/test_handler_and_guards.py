import io
import json
from pathlib import Path
import pytest

from src.ingestion_lambda.handler import lambda_handler
from src.ingestion_lambda.schema import (
    RecursiveTriggerGuardError,
    SchemaValidationError,
)
from src.ingestion_lambda.storage_adapter import (
    LocalFilesystemS3Backend,
    S3StorageBackend,
)


def make_s3_event(bucket: str, key: str) -> dict:
    return {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": bucket},
                    "object": {"key": key},
                }
            }
        ]
    }


def test_lambda_handler_processes_url_encoded_s3_key_and_writes_partitions(
    tmp_path: Path,
) -> None:
    storage = LocalFilesystemS3Backend(root_directory=tmp_path)
    bucket = "retail-datalake-test"
    raw_key = "raw/transactions/store batch+2026.csv"
    encoded_key = "raw/transactions/store+batch%2B2026.csv"

    csv_body = (
        "transaction_id,transaction_timestamp,store_id,customer_id,product_sku,"
        "category,quantity,unit_price,discount_amount,payment_method,currency\n"
        "TXN-9001A,2026-10-28T09:00:00Z,STORE-001,CUST-1001,SKU-ELEC-01,"
        "Electronics,1,100.00,10.00,CARD,USD\n"
        "TXN-9002B,2026-10-28T10:00:00Z,STORE-001,GUEST,SKU-GROC-01,"
        "Grocery,0,10.00,0.00,CASH,USD\n"
    )
    storage.put_text_object(bucket=bucket, key=raw_key, body=csv_body)

    response = lambda_handler(
        event=make_s3_event(bucket=bucket, key=encoded_key),
        context=None,
        storage_backend=storage,
    )

    assert response["status"] == "SUCCESS"
    assert response["processed_count"] == 1
    summary = response["processed_batches"][0]
    assert summary["valid_row_count"] == 1
    assert summary["quarantined_row_count"] == 1
    assert len(summary["curated_keys_written"]) == 1
    assert summary["quarantine_key_written"] is not None

    quarantine_doc = json.loads(
        storage.get_text_object(bucket, summary["quarantine_key_written"])
    )
    assert quarantine_doc["summary"]["quarantined_row_count"] == 1


def test_lambda_handler_records_file_error_and_raises_on_malformed_schema(
    tmp_path: Path,
) -> None:
    storage = LocalFilesystemS3Backend(root_directory=tmp_path)
    bucket = "retail-datalake-test"
    raw_key = "raw/transactions/bad_headers.csv"
    storage.put_text_object(
        bucket=bucket,
        key=raw_key,
        body="transaction_id,store_id\nTXN-1001,STORE-001\n",
    )

    with pytest.raises(SchemaValidationError):
        lambda_handler(
            event=make_s3_event(bucket=bucket, key=raw_key),
            context=None,
            storage_backend=storage,
        )

    file_errors_dir = (
        tmp_path / bucket / "quarantine" / "transactions" / "file_errors"
    )
    error_files = list(file_errors_dir.rglob("*_schema_error.json"))
    assert len(error_files) == 1
    report = json.loads(error_files[0].read_text(encoding="utf-8"))
    assert "missing required columns" in report["file_level_error"]


def test_lambda_handler_blocks_recursive_trigger_from_curated_prefix(
    tmp_path: Path,
) -> None:
    storage = LocalFilesystemS3Backend(root_directory=tmp_path)
    with pytest.raises(RecursiveTriggerGuardError):
        lambda_handler(
            event=make_s3_event(
                bucket="retail-datalake-test",
                key="curated/transactions/transaction_date=2026-10-28/part.csv",
            ),
            context=None,
            storage_backend=storage,
        )


def test_s3_storage_backend_uses_mock_client_correctly() -> None:
    calls = []

    class DummyS3Client:
        def get_object(self, Bucket: str, Key: str) -> dict:
            return {"Body": io.BytesIO(b"col1,col2\nval1,val2\n")}

        def put_object(self, **kwargs: object) -> None:
            calls.append(kwargs)

    backend = S3StorageBackend(s3_client=DummyS3Client())
    text = backend.get_text_object("my-bucket", "raw/transactions/file.csv")
    assert "val1,val2" in text

    backend.put_text_object(
        bucket="my-bucket",
        key="curated/transactions/out.csv",
        body=text,
        content_type="text/csv",
        metadata={"batch_id": "b1"},
    )
    assert len(calls) == 1
    assert calls[0]["ServerSideEncryption"] == "AES256"
    assert calls[0]["Metadata"] == {"batch_id": "b1"}
