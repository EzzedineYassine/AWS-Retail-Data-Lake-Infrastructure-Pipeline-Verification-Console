import csv
import io
import json
from typing import Dict, List, Optional, Set, Tuple

from .schema import (
    CURATED_CSV_COLUMNS,
    QuarantinedRowRecord,
    ValidatedTransactionRecord,
)
from .validator import (
    validate_and_parse_row,
    validate_csv_headers,
)


def parse_and_transform_csv_stream(
    csv_content: str,
    source_file: str,
    ingested_at_utc: str,
) -> Tuple[Dict[str, List[ValidatedTransactionRecord]], List[QuarantinedRowRecord], int]:
    cleaned_content = csv_content.lstrip("\ufeff")
    stream = io.StringIO(cleaned_content)
    reader = csv.DictReader(stream)

    validate_csv_headers(reader.fieldnames)

    partitions: Dict[str, List[ValidatedTransactionRecord]] = {}
    quarantined_rows: List[QuarantinedRowRecord] = []
    seen_transaction_ids: Set[str] = set()
    total_rows = 0

    for row_index, raw_row in enumerate(reader, start=2):
        if all((v is None or str(v).strip() == "") for v in raw_row.values()):
            continue

        total_rows += 1
        outcome = validate_and_parse_row(
            raw_row=raw_row,
            row_number=row_index,
            seen_transaction_ids=seen_transaction_ids,
            source_file=source_file,
            ingested_at_utc=ingested_at_utc,
        )

        if isinstance(outcome, ValidatedTransactionRecord):
            partition_bucket = partitions.setdefault(outcome.transaction_date, [])
            partition_bucket.append(outcome)
        else:
            quarantined_rows.append(outcome)

    for date_key in partitions:
        partitions[date_key].sort(
            key=lambda rec: (rec.transaction_timestamp, rec.transaction_id)
        )

    return partitions, quarantined_rows, total_rows


def serialize_curated_partition_csv(
    records: List[ValidatedTransactionRecord],
) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=list(CURATED_CSV_COLUMNS),
        lineterminator="\n",
        quoting=csv.QUOTE_MINIMAL,
    )
    writer.writeheader()
    for record in records:
        writer.writerow(record.to_curated_row_dict())
    return output.getvalue()


def serialize_quarantine_payload(
    batch_id: str,
    source_bucket: str,
    source_key: str,
    ingested_at_utc: str,
    total_rows_read: int,
    valid_row_count: int,
    quarantined_rows: List[QuarantinedRowRecord],
    file_level_error: Optional[str] = None,
) -> str:
    error_code_counts: Dict[str, int] = {}
    for row in quarantined_rows:
        for code in row.error_codes:
            error_code_counts[code] = error_code_counts.get(code, 0) + 1

    payload = {
        "batch_id": batch_id,
        "source_bucket": source_bucket,
        "source_key": source_key,
        "ingested_at_utc": ingested_at_utc,
        "file_level_error": file_level_error,
        "summary": {
            "total_rows_read": total_rows_read,
            "valid_row_count": valid_row_count,
            "quarantined_row_count": len(quarantined_rows),
            "error_code_breakdown": error_code_counts,
        },
        "rejected_rows": [row.to_dict() for row in quarantined_rows],
    }
    return json.dumps(payload, indent=2, sort_keys=True)
