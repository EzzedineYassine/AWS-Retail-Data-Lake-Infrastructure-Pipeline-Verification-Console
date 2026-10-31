from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import PurePosixPath
from typing import Any, Dict, List, Optional
import urllib.parse

from .schema import (
    BatchProcessingResult,
    RecursiveTriggerGuardError,
    SchemaValidationError,
)
from .storage_adapter import (
    DataLakeStorageBackend,
    S3StorageBackend,
)
from .transformer import (
    parse_and_transform_csv_stream,
    serialize_curated_partition_csv,
    serialize_quarantine_payload,
)
from .validator import (
    validate_object_key_against_recursive_trigger,
)

logger = logging.getLogger("retail_datalake_ingestion")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())


def emit_structured_log(level: str, event_type: str, **fields: Any) -> Dict[str, Any]:
    payload = {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "level": level.upper(),
        "event_type": event_type,
        **fields,
    }
    serialized = json.dumps(payload, sort_keys=True)
    if level.upper() == "ERROR":
        logger.error(serialized)
    elif level.upper() == "WARNING":
        logger.warning(serialized)
    else:
        logger.info(serialized)
    return payload


def compute_deterministic_batch_id(source_key: str, csv_content: str) -> str:
    stem = PurePosixPath(source_key).stem
    digest = hashlib.sha256(csv_content.encode("utf-8")).hexdigest()[:10]
    return f"{stem}_{digest}"


def process_single_s3_object(
    source_bucket: str,
    raw_object_key: str,
    storage: DataLakeStorageBackend,
    target_bucket: Optional[str] = None,
    raw_prefix: str = "raw/transactions/",
    curated_prefix: str = "curated/transactions/",
    quarantine_prefix: str = "quarantine/transactions/",
    ingested_at_override: Optional[str] = None,
) -> BatchProcessingResult:
    destination_bucket = target_bucket or source_bucket
    ingested_at_utc = ingested_at_override or datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    ingestion_date = ingested_at_utc[:10]

    normalized_key = validate_object_key_against_recursive_trigger(
        object_key=raw_object_key,
        raw_prefix=raw_prefix,
        forbidden_prefixes=(
            curated_prefix.split("/")[0] + "/",
            quarantine_prefix.split("/")[0] + "/",
            "athena-results/",
        ),
    )

    csv_content = storage.get_text_object(bucket=source_bucket, key=normalized_key)
    batch_id = compute_deterministic_batch_id(normalized_key, csv_content)

    result = BatchProcessingResult(
        batch_id=batch_id,
        source_bucket=source_bucket,
        source_key=normalized_key,
        ingested_at_utc=ingested_at_utc,
    )

    try:
        partitions, quarantined_rows, total_rows = parse_and_transform_csv_stream(
            csv_content=csv_content,
            source_file=normalized_key,
            ingested_at_utc=ingested_at_utc,
        )
    except SchemaValidationError as exc:
        quarantine_error_key = (
            f"{quarantine_prefix.rstrip('/')}/file_errors/"
            f"ingestion_date={ingestion_date}/{batch_id}_schema_error.json"
        )
        error_report = serialize_quarantine_payload(
            batch_id=batch_id,
            source_bucket=source_bucket,
            source_key=normalized_key,
            ingested_at_utc=ingested_at_utc,
            total_rows_read=0,
            valid_row_count=0,
            quarantined_rows=[],
            file_level_error=str(exc),
        )
        storage.put_text_object(
            bucket=destination_bucket,
            key=quarantine_error_key,
            body=error_report,
            content_type="application/json",
            metadata={
                "source_key": normalized_key,
                "failure_type": "SCHEMA_VALIDATION_ERROR",
            },
        )
        emit_structured_log(
            level="ERROR",
            event_type="FILE_VALIDATION_FAILURE",
            batch_id=batch_id,
            source_bucket=source_bucket,
            source_key=normalized_key,
            quarantine_key=quarantine_error_key,
            missing_columns=list(exc.missing_columns),
            error_message=str(exc),
        )
        raise

    result.total_rows_read = total_rows
    valid_count = 0

    for transaction_date, records in sorted(partitions.items()):
        valid_count += len(records)
        result.partition_row_counts[transaction_date] = len(records)
        curated_key = (
            f"{curated_prefix.rstrip('/')}/"
            f"transaction_date={transaction_date}/{batch_id}.csv"
        )
        curated_csv = serialize_curated_partition_csv(records)
        storage.put_text_object(
            bucket=destination_bucket,
            key=curated_key,
            body=curated_csv,
            content_type="text/csv",
            metadata={
                "batch_id": batch_id,
                "source_key": normalized_key,
                "row_count": str(len(records)),
                "transaction_date": transaction_date,
            },
        )
        result.curated_keys_written.append(curated_key)

    result.valid_row_count = valid_count
    result.quarantined_row_count = len(quarantined_rows)

    if quarantined_rows:
        quarantine_key = (
            f"{quarantine_prefix.rstrip('/')}/rejected_rows/"
            f"ingestion_date={ingestion_date}/{batch_id}_rejected.json"
        )
        quarantine_json = serialize_quarantine_payload(
            batch_id=batch_id,
            source_bucket=source_bucket,
            source_key=normalized_key,
            ingested_at_utc=ingested_at_utc,
            total_rows_read=total_rows,
            valid_row_count=valid_count,
            quarantined_rows=quarantined_rows,
        )
        storage.put_text_object(
            bucket=destination_bucket,
            key=quarantine_key,
            body=quarantine_json,
            content_type="application/json",
            metadata={
                "batch_id": batch_id,
                "source_key": normalized_key,
                "quarantined_row_count": str(len(quarantined_rows)),
            },
        )
        result.quarantine_key_written = quarantine_key
        emit_structured_log(
            level="WARNING",
            event_type="QUARANTINE_ROWS_DETECTED",
            batch_id=batch_id,
            source_bucket=source_bucket,
            source_key=normalized_key,
            quarantined_row_count=len(quarantined_rows),
            valid_row_count=valid_count,
            quarantine_key=quarantine_key,
        )

    emit_structured_log(
        level="INFO",
        event_type="BATCH_PROCESSING_COMPLETED",
        **result.to_summary_dict(),
    )
    return result


def lambda_handler(
    event: Dict[str, Any],
    context: Optional[Any] = None,
    storage_backend: Optional[DataLakeStorageBackend] = None,
) -> Dict[str, Any]:
    storage = storage_backend or S3StorageBackend()
    raw_prefix = os.environ.get("RAW_PREFIX", "raw/transactions/")
    curated_prefix = os.environ.get("CURATED_PREFIX", "curated/transactions/")
    quarantine_prefix = os.environ.get("QUARANTINE_PREFIX", "quarantine/transactions/")
    configured_bucket = os.environ.get("DATA_LAKE_BUCKET")
    ingested_at_override = os.environ.get("INGESTED_AT_OVERRIDE")

    records = event.get("Records", [])
    if not records:
        emit_structured_log(
            level="WARNING",
            event_type="EMPTY_EVENT_RECORDS",
            message="No S3 event records present in invocation payload",
        )
        return {"status": "NO_OP", "processed_batches": []}

    processed_batches: List[Dict[str, Any]] = []

    for record in records:
        s3_info = record.get("s3", {})
        bucket_name = s3_info.get("bucket", {}).get("name") or configured_bucket
        raw_encoded_key = s3_info.get("object", {}).get("key", "")
        decoded_key = urllib.parse.unquote_plus(raw_encoded_key)

        if not bucket_name:
            raise ValueError("Missing source S3 bucket name in event and environment")

        try:
            batch_result = process_single_s3_object(
                source_bucket=bucket_name,
                raw_object_key=decoded_key,
                storage=storage,
                target_bucket=configured_bucket or bucket_name,
                raw_prefix=raw_prefix,
                curated_prefix=curated_prefix,
                quarantine_prefix=quarantine_prefix,
                ingested_at_override=ingested_at_override,
            )
            processed_batches.append(batch_result.to_summary_dict())
        except RecursiveTriggerGuardError as guard_err:
            emit_structured_log(
                level="ERROR",
                event_type="RECURSIVE_TRIGGER_GUARD_BLOCKED",
                source_bucket=bucket_name,
                source_key=decoded_key,
                error_message=str(guard_err),
            )
            raise

    return {
        "status": "SUCCESS",
        "processed_count": len(processed_batches),
        "processed_batches": processed_batches,
    }
