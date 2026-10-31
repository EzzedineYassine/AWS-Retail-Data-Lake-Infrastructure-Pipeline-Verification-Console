from decimal import Decimal
import pytest

from src.ingestion_lambda.schema import (
    QuarantinedRowRecord,
    REQUIRED_RAW_COLUMNS,
    RecursiveTriggerGuardError,
    SchemaValidationError,
    ValidatedTransactionRecord,
)
from src.ingestion_lambda.validator import (
    parse_iso_timestamp,
    validate_and_parse_row,
    validate_csv_headers,
    validate_object_key_against_recursive_trigger,
)


def make_valid_raw_row(**overrides: str) -> dict:
    base = {
        "transaction_id": "TXN-20261028001",
        "transaction_timestamp": "2026-10-28T14:30:00Z",
        "store_id": "STORE-001",
        "customer_id": "CUST-1001A",
        "product_sku": "SKU-ELEC-401",
        "category": "Electronics",
        "quantity": "2",
        "unit_price": "150.00",
        "discount_amount": "25.00",
        "payment_method": "CARD",
        "currency": "USD",
    }
    base.update(overrides)
    return base


def test_recursive_trigger_guard_accepts_valid_raw_csv_key() -> None:
    key = "raw/transactions/2026/10/retail_batch_01.csv"
    assert validate_object_key_against_recursive_trigger(key) == key


@pytest.mark.parametrize(
    "forbidden_key",
    [
        "curated/transactions/transaction_date=2026-10-28/batch.csv",
        "quarantine/transactions/rejected_rows/batch_rejected.json",
        "athena-results/Unsaved/2026/10/28/query.csv",
        "archive/transactions/batch.csv",
        "raw/transactions/readme.txt",
        "",
    ],
)
def test_recursive_trigger_guard_blocks_non_raw_or_non_csv_keys(
    forbidden_key: str,
) -> None:
    with pytest.raises(RecursiveTriggerGuardError):
        validate_object_key_against_recursive_trigger(forbidden_key)


def test_validate_csv_headers_accepts_exact_schema() -> None:
    headers = validate_csv_headers(list(REQUIRED_RAW_COLUMNS))
    assert headers == REQUIRED_RAW_COLUMNS


def test_validate_csv_headers_rejects_missing_columns() -> None:
    incomplete = ["transaction_id", "store_id", "quantity"]
    with pytest.raises(SchemaValidationError) as exc_info:
        validate_csv_headers(incomplete)
    assert "unit_price" in exc_info.value.missing_columns
    assert "currency" in exc_info.value.missing_columns


def test_parse_iso_timestamp_normalizes_timezone_to_utc() -> None:
    norm_ts, part_date = parse_iso_timestamp("2026-10-28T23:30:00-02:00")
    assert norm_ts == "2026-10-29 01:30:00"
    assert part_date == "2026-10-29"


def test_validate_and_parse_row_produces_validated_record() -> None:
    seen = set()
    outcome = validate_and_parse_row(
        raw_row=make_valid_raw_row(),
        row_number=2,
        seen_transaction_ids=seen,
        source_file="raw/transactions/sample.csv",
        ingested_at_utc="2026-10-30T12:00:00Z",
    )
    assert isinstance(outcome, ValidatedTransactionRecord)
    assert outcome.transaction_id == "TXN-20261028001"
    assert outcome.transaction_date == "2026-10-28"
    assert outcome.gross_amount == Decimal("300.00")
    assert outcome.net_amount == Decimal("275.00")
    assert "TXN-20261028001" in seen


def test_validate_and_parse_row_flags_duplicate_transaction_id() -> None:
    seen = {"TXN-20261028001"}
    outcome = validate_and_parse_row(
        raw_row=make_valid_raw_row(),
        row_number=5,
        seen_transaction_ids=seen,
        source_file="raw/transactions/sample.csv",
        ingested_at_utc="2026-10-30T12:00:00Z",
    )
    assert isinstance(outcome, QuarantinedRowRecord)
    assert "DUPLICATE_TRANSACTION_ID" in outcome.error_codes


@pytest.mark.parametrize(
    "overrides,expected_error_code",
    [
        ({"transaction_id": "BAD_ID"}, "INVALID_TRANSACTION_ID"),
        ({"transaction_timestamp": "not-a-timestamp"}, "INVALID_TIMESTAMP"),
        ({"store_id": "MALL-01"}, "INVALID_STORE_ID"),
        ({"customer_id": "INVALID#USER"}, "INVALID_CUSTOMER_ID"),
        ({"product_sku": ""}, "INVALID_PRODUCT_SKU"),
        ({"category": ""}, "INVALID_CATEGORY"),
        ({"quantity": "-5"}, "INVALID_QUANTITY"),
        ({"quantity": "0"}, "INVALID_QUANTITY"),
        ({"unit_price": "0.00"}, "INVALID_UNIT_PRICE"),
        ({"unit_price": "abc"}, "INVALID_UNIT_PRICE"),
        ({"discount_amount": "-1.00"}, "NEGATIVE_DISCOUNT"),
        ({"discount_amount": "350.00"}, "DISCOUNT_EXCEEDS_GROSS_AMOUNT"),
        ({"payment_method": "CRYPTO"}, "UNSUPPORTED_PAYMENT_METHOD"),
        ({"currency": "CHF"}, "UNSUPPORTED_CURRENCY"),
    ],
)
def test_validate_and_parse_row_deterministic_rejection_codes(
    overrides: dict, expected_error_code: str
) -> None:
    outcome = validate_and_parse_row(
        raw_row=make_valid_raw_row(**overrides),
        row_number=3,
        seen_transaction_ids=set(),
        source_file="raw/transactions/sample.csv",
        ingested_at_utc="2026-10-30T12:00:00Z",
    )
    assert isinstance(outcome, QuarantinedRowRecord)
    assert expected_error_code in outcome.error_codes
