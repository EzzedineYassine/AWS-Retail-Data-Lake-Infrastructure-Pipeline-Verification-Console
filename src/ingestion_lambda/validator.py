from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Dict, List, Optional, Sequence, Set, Tuple, Union

from .schema import (
    ALLOWED_CURRENCIES,
    ALLOWED_PAYMENT_METHODS,
    CUSTOMER_ID_PATTERN,
    PRODUCT_SKU_PATTERN,
    QuarantinedRowRecord,
    REQUIRED_RAW_COLUMNS,
    RecursiveTriggerGuardError,
    STORE_ID_PATTERN,
    SchemaValidationError,
    TRANSACTION_ID_PATTERN,
    ValidatedTransactionRecord,
)

TWO_DECIMAL_PLACES = Decimal("0.01")


def validate_object_key_against_recursive_trigger(
    object_key: str,
    raw_prefix: str = "raw/transactions/",
    forbidden_prefixes: Sequence[str] = (
        "curated/",
        "quarantine/",
        "athena-results/",
    ),
) -> str:
    normalized_key = object_key.strip().lstrip("/")
    if not normalized_key:
        raise RecursiveTriggerGuardError("Object key cannot be empty")

    for forbidden_prefix in forbidden_prefixes:
        if normalized_key.startswith(forbidden_prefix):
            raise RecursiveTriggerGuardError(
                f"Recursive trigger blocked: key '{normalized_key}' belongs to protected prefix '{forbidden_prefix}'"
            )

    if not normalized_key.startswith(raw_prefix):
        raise RecursiveTriggerGuardError(
            f"Invalid ingestion source: key '{normalized_key}' must start with '{raw_prefix}'"
        )

    if not normalized_key.lower().endswith(".csv"):
        raise RecursiveTriggerGuardError(
            f"Unsupported file extension for key '{normalized_key}': expected '.csv'"
        )

    return normalized_key


def validate_csv_headers(fieldnames: Optional[Sequence[str]]) -> Tuple[str, ...]:
    if not fieldnames:
        raise SchemaValidationError(
            "CSV file has no header row or is empty",
            missing_columns=REQUIRED_RAW_COLUMNS,
        )

    normalized_headers = tuple(col.strip() for col in fieldnames if col is not None)
    header_set = set(normalized_headers)
    required_set = set(REQUIRED_RAW_COLUMNS)

    missing = tuple(col for col in REQUIRED_RAW_COLUMNS if col not in header_set)
    unexpected = tuple(col for col in normalized_headers if col not in required_set)

    if missing:
        raise SchemaValidationError(
            f"CSV header validation failed: missing required columns {list(missing)}",
            missing_columns=missing,
            unexpected_columns=unexpected,
        )

    return normalized_headers


def parse_iso_timestamp(raw_timestamp: str) -> Tuple[str, str]:
    cleaned = raw_timestamp.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    parsed_dt = datetime.fromisoformat(cleaned)
    if parsed_dt.tzinfo is not None:
        parsed_dt = parsed_dt.astimezone(timezone.utc).replace(tzinfo=None)
    normalized_timestamp = parsed_dt.strftime("%Y-%m-%d %H:%M:%S")
    partition_date = parsed_dt.strftime("%Y-%m-%d")
    return normalized_timestamp, partition_date


def parse_non_negative_decimal(raw_value: str) -> Decimal:
    decimal_val = Decimal(raw_value.strip())
    if not decimal_val.is_finite():
        raise InvalidOperation("Non-finite decimal")
    return decimal_val.quantize(TWO_DECIMAL_PLACES, rounding=ROUND_HALF_UP)


def validate_and_parse_row(
    raw_row: Dict[str, Optional[str]],
    row_number: int,
    seen_transaction_ids: Set[str],
    source_file: str,
    ingested_at_utc: str,
) -> Union[ValidatedTransactionRecord, QuarantinedRowRecord]:
    error_codes: List[str] = []
    error_messages: List[str] = []

    if None in raw_row:
        error_codes.append("MALFORMED_COLUMN_COUNT")
        error_messages.append("Row contains extra unmapped fields beyond header columns")

    sanitized_row: Dict[str, Optional[str]] = {
        str(k): (v.strip() if isinstance(v, str) else v)
        for k, v in raw_row.items()
        if k is not None
    }

    transaction_id = (sanitized_row.get("transaction_id") or "").upper()
    if not transaction_id or not TRANSACTION_ID_PATTERN.match(transaction_id):
        error_codes.append("INVALID_TRANSACTION_ID")
        error_messages.append(
            f"transaction_id '{transaction_id}' does not match TXN-<ALPHANUMERIC>"
        )
    elif transaction_id in seen_transaction_ids:
        error_codes.append("DUPLICATE_TRANSACTION_ID")
        error_messages.append(
            f"Duplicate transaction_id '{transaction_id}' encountered in same batch"
        )

    raw_ts = sanitized_row.get("transaction_timestamp") or ""
    normalized_timestamp = ""
    transaction_date = ""
    if not raw_ts:
        error_codes.append("MISSING_TIMESTAMP")
        error_messages.append("transaction_timestamp is required")
    else:
        try:
            normalized_timestamp, transaction_date = parse_iso_timestamp(raw_ts)
        except ValueError:
            error_codes.append("INVALID_TIMESTAMP")
            error_messages.append(
                f"transaction_timestamp '{raw_ts}' is not a valid ISO-8601 timestamp"
            )

    store_id = (sanitized_row.get("store_id") or "").upper()
    if not store_id or not STORE_ID_PATTERN.match(store_id):
        error_codes.append("INVALID_STORE_ID")
        error_messages.append(
            f"store_id '{store_id}' must match pattern STORE-<DIGITS>"
        )

    customer_id = (sanitized_row.get("customer_id") or "GUEST").upper()
    if not CUSTOMER_ID_PATTERN.match(customer_id):
        error_codes.append("INVALID_CUSTOMER_ID")
        error_messages.append(
            f"customer_id '{customer_id}' must match CUST-<ALPHANUMERIC> or GUEST"
        )

    product_sku = (sanitized_row.get("product_sku") or "").upper()
    if not product_sku or not PRODUCT_SKU_PATTERN.match(product_sku):
        error_codes.append("INVALID_PRODUCT_SKU")
        error_messages.append(
            f"product_sku '{product_sku}' must match SKU-<ALPHANUMERIC>"
        )

    raw_category = sanitized_row.get("category") or ""
    category = raw_category.strip().title()
    if not category or len(category) > 64:
        error_codes.append("INVALID_CATEGORY")
        error_messages.append("category must be a non-empty string up to 64 characters")

    raw_quantity = sanitized_row.get("quantity") or ""
    quantity = 0
    try:
        quantity = int(raw_quantity)
        if str(quantity) != raw_quantity.strip() or quantity <= 0 or quantity > 10000:
            raise ValueError("Out of bounds")
    except ValueError:
        error_codes.append("INVALID_QUANTITY")
        error_messages.append(
            f"quantity '{raw_quantity}' must be a positive integer between 1 and 10000"
        )

    raw_unit_price = sanitized_row.get("unit_price") or ""
    unit_price = Decimal("0.00")
    unit_price_valid = False
    try:
        unit_price = parse_non_negative_decimal(raw_unit_price)
        if unit_price <= Decimal("0.00"):
            error_codes.append("INVALID_UNIT_PRICE")
            error_messages.append(
                f"unit_price '{raw_unit_price}' must be strictly greater than 0.00"
            )
        else:
            unit_price_valid = True
    except (InvalidOperation, ValueError):
        error_codes.append("INVALID_UNIT_PRICE")
        error_messages.append(f"unit_price '{raw_unit_price}' is not a valid decimal")

    raw_discount = sanitized_row.get("discount_amount") or "0.00"
    discount_amount = Decimal("0.00")
    discount_valid = False
    try:
        discount_amount = parse_non_negative_decimal(raw_discount)
        if discount_amount < Decimal("0.00"):
            error_codes.append("NEGATIVE_DISCOUNT")
            error_messages.append(
                f"discount_amount '{raw_discount}' cannot be negative"
            )
        else:
            discount_valid = True
    except (InvalidOperation, ValueError):
        error_codes.append("INVALID_DISCOUNT_AMOUNT")
        error_messages.append(
            f"discount_amount '{raw_discount}' is not a valid decimal"
        )

    gross_amount = Decimal("0.00")
    net_amount = Decimal("0.00")
    if quantity > 0 and unit_price_valid and discount_valid:
        gross_amount = (Decimal(quantity) * unit_price).quantize(
            TWO_DECIMAL_PLACES, rounding=ROUND_HALF_UP
        )
        if discount_amount > gross_amount:
            error_codes.append("DISCOUNT_EXCEEDS_GROSS_AMOUNT")
            error_messages.append(
                f"discount_amount ({discount_amount:.2f}) exceeds gross_amount ({gross_amount:.2f})"
            )
        else:
            net_amount = (gross_amount - discount_amount).quantize(
                TWO_DECIMAL_PLACES, rounding=ROUND_HALF_UP
            )

    payment_method = (sanitized_row.get("payment_method") or "").upper()
    if payment_method not in ALLOWED_PAYMENT_METHODS:
        error_codes.append("UNSUPPORTED_PAYMENT_METHOD")
        error_messages.append(
            f"payment_method '{payment_method}' is not in {sorted(ALLOWED_PAYMENT_METHODS)}"
        )

    currency = (sanitized_row.get("currency") or "").upper()
    if currency not in ALLOWED_CURRENCIES:
        error_codes.append("UNSUPPORTED_CURRENCY")
        error_messages.append(
            f"currency '{currency}' is not in {sorted(ALLOWED_CURRENCIES)}"
        )

    if error_codes:
        return QuarantinedRowRecord(
            row_number=row_number,
            error_codes=tuple(error_codes),
            error_messages=tuple(error_messages),
            raw_row=sanitized_row,
        )

    seen_transaction_ids.add(transaction_id)
    return ValidatedTransactionRecord(
        transaction_id=transaction_id,
        transaction_timestamp=normalized_timestamp,
        transaction_date=transaction_date,
        store_id=store_id,
        customer_id=customer_id,
        product_sku=product_sku,
        category=category,
        quantity=quantity,
        unit_price=unit_price,
        discount_amount=discount_amount,
        gross_amount=gross_amount,
        net_amount=net_amount,
        payment_method=payment_method,
        currency=currency,
        source_file=source_file,
        ingested_at_utc=ingested_at_utc,
    )
