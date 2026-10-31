from dataclasses import dataclass, field
from decimal import Decimal
import re
from typing import Dict, List, Optional, Tuple

REQUIRED_RAW_COLUMNS: Tuple[str, ...] = (
    "transaction_id",
    "transaction_timestamp",
    "store_id",
    "customer_id",
    "product_sku",
    "category",
    "quantity",
    "unit_price",
    "discount_amount",
    "payment_method",
    "currency",
)

CURATED_CSV_COLUMNS: Tuple[str, ...] = (
    "transaction_id",
    "transaction_timestamp",
    "store_id",
    "customer_id",
    "product_sku",
    "category",
    "quantity",
    "unit_price",
    "discount_amount",
    "gross_amount",
    "net_amount",
    "payment_method",
    "currency",
    "source_file",
    "ingested_at_utc",
)

ALLOWED_PAYMENT_METHODS: frozenset[str] = frozenset(
    {"CARD", "CASH", "MOBILE_PAY", "VOUCHER"}
)

ALLOWED_CURRENCIES: frozenset[str] = frozenset({"USD", "EUR", "GBP"})

TRANSACTION_ID_PATTERN = re.compile(r"^TXN-[A-Z0-9]{4,24}$")
STORE_ID_PATTERN = re.compile(r"^STORE-[0-9]{3,6}$")
CUSTOMER_ID_PATTERN = re.compile(r"^(CUST-[A-Z0-9]{4,16}|GUEST)$")
PRODUCT_SKU_PATTERN = re.compile(r"^SKU-[A-Z0-9-]{3,20}$")


class RecursiveTriggerGuardError(ValueError):
    pass


class SchemaValidationError(ValueError):
    def __init__(
        self,
        message: str,
        missing_columns: Tuple[str, ...] = (),
        unexpected_columns: Tuple[str, ...] = (),
    ) -> None:
        super().__init__(message)
        self.missing_columns = missing_columns
        self.unexpected_columns = unexpected_columns


@dataclass(frozen=True)
class ValidatedTransactionRecord:
    transaction_id: str
    transaction_timestamp: str
    transaction_date: str
    store_id: str
    customer_id: str
    product_sku: str
    category: str
    quantity: int
    unit_price: Decimal
    discount_amount: Decimal
    gross_amount: Decimal
    net_amount: Decimal
    payment_method: str
    currency: str
    source_file: str
    ingested_at_utc: str

    def to_curated_row_dict(self) -> Dict[str, str]:
        return {
            "transaction_id": self.transaction_id,
            "transaction_timestamp": self.transaction_timestamp,
            "store_id": self.store_id,
            "customer_id": self.customer_id,
            "product_sku": self.product_sku,
            "category": self.category,
            "quantity": str(self.quantity),
            "unit_price": f"{self.unit_price:.2f}",
            "discount_amount": f"{self.discount_amount:.2f}",
            "gross_amount": f"{self.gross_amount:.2f}",
            "net_amount": f"{self.net_amount:.2f}",
            "payment_method": self.payment_method,
            "currency": self.currency,
            "source_file": self.source_file,
            "ingested_at_utc": self.ingested_at_utc,
        }


@dataclass(frozen=True)
class QuarantinedRowRecord:
    row_number: int
    error_codes: Tuple[str, ...]
    error_messages: Tuple[str, ...]
    raw_row: Dict[str, Optional[str]]

    def to_dict(self) -> Dict[str, object]:
        return {
            "row_number": self.row_number,
            "error_codes": list(self.error_codes),
            "error_messages": list(self.error_messages),
            "raw_row": self.raw_row,
        }


@dataclass
class BatchProcessingResult:
    batch_id: str
    source_bucket: str
    source_key: str
    ingested_at_utc: str
    total_rows_read: int = 0
    valid_row_count: int = 0
    quarantined_row_count: int = 0
    curated_keys_written: List[str] = field(default_factory=list)
    quarantine_key_written: Optional[str] = None
    partition_row_counts: Dict[str, int] = field(default_factory=dict)

    def to_summary_dict(self) -> Dict[str, object]:
        return {
            "batch_id": self.batch_id,
            "source_bucket": self.source_bucket,
            "source_key": self.source_key,
            "ingested_at_utc": self.ingested_at_utc,
            "total_rows_read": self.total_rows_read,
            "valid_row_count": self.valid_row_count,
            "quarantined_row_count": self.quarantined_row_count,
            "curated_keys_written": self.curated_keys_written,
            "quarantine_key_written": self.quarantine_key_written,
            "partition_row_counts": self.partition_row_counts,
        }
