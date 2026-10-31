import csv
import io
import json

from src.ingestion_lambda.schema import CURATED_CSV_COLUMNS
from src.ingestion_lambda.transformer import (
    parse_and_transform_csv_stream,
    serialize_curated_partition_csv,
    serialize_quarantine_payload,
)


SAMPLE_MIXED_CSV = """transaction_id,transaction_timestamp,store_id,customer_id,product_sku,category,quantity,unit_price,discount_amount,payment_method,currency
TXN-1001A,2026-10-27T10:00:00Z,STORE-001,CUST-1001,SKU-ELEC-01,Electronics,2,50.00,10.00,CARD,USD
TXN-1002B,2026-10-28T11:30:00Z,STORE-002,GUEST,SKU-GROC-02,Grocery,4,5.25,0.00,CASH,USD
TXN-1003C,2026-10-28T12:00:00Z,STORE-001,CUST-1002,SKU-APPR-03,Apparel,-2,30.00,0.00,CARD,USD
"""


def test_parse_and_transform_splits_partitions_and_quarantines_bad_rows() -> None:
    partitions, quarantined, total_rows = parse_and_transform_csv_stream(
        csv_content=SAMPLE_MIXED_CSV,
        source_file="raw/transactions/batch.csv",
        ingested_at_utc="2026-10-30T12:00:00Z",
    )
    assert total_rows == 3
    assert sorted(partitions.keys()) == ["2026-10-27", "2026-10-28"]
    assert len(partitions["2026-10-27"]) == 1
    assert len(partitions["2026-10-28"]) == 1
    assert len(quarantined) == 1
    assert quarantined[0].row_number == 4
    assert "INVALID_QUANTITY" in quarantined[0].error_codes


def test_serialize_curated_partition_csv_matches_glue_table_columns() -> None:
    partitions, _, _ = parse_and_transform_csv_stream(
        csv_content=SAMPLE_MIXED_CSV,
        source_file="raw/transactions/batch.csv",
        ingested_at_utc="2026-10-30T12:00:00Z",
    )
    csv_text = serialize_curated_partition_csv(partitions["2026-10-27"])
    reader = csv.DictReader(io.StringIO(csv_text))
    assert tuple(reader.fieldnames or ()) == CURATED_CSV_COLUMNS
    rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["gross_amount"] == "100.00"
    assert rows[0]["net_amount"] == "90.00"


def test_serialize_quarantine_payload_includes_error_breakdown() -> None:
    _, quarantined, total_rows = parse_and_transform_csv_stream(
        csv_content=SAMPLE_MIXED_CSV,
        source_file="raw/transactions/batch.csv",
        ingested_at_utc="2026-10-30T12:00:00Z",
    )
    payload_str = serialize_quarantine_payload(
        batch_id="batch_123",
        source_bucket="retail-bucket",
        source_key="raw/transactions/batch.csv",
        ingested_at_utc="2026-10-30T12:00:00Z",
        total_rows_read=total_rows,
        valid_row_count=2,
        quarantined_rows=quarantined,
    )
    parsed = json.loads(payload_str)
    assert parsed["summary"]["quarantined_row_count"] == 1
    assert parsed["summary"]["error_code_breakdown"]["INVALID_QUANTITY"] == 1
    assert len(parsed["rejected_rows"]) == 1
