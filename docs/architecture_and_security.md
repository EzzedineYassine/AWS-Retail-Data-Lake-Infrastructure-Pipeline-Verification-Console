# Architecture, Security Controls, and Data Governance

## 1. Architectural Decisions and Trade-offs

Small and mid-sized retailers need reliable, auditable analytics over point-of-sale (POS) and e-commerce CSV exports without the fixed infrastructure cost or operational burden of always-on clusters. Every component in this architecture was chosen to minimize idle cost, operational complexity, and blast radius.

| Decision Area | Selected Pattern | Alternative Considered | Engineering Rationale |
| :--- | :--- | :--- | :--- |
| **Storage Layout** | Single S3 Data Lake bucket with strict prefix isolation (`raw/`, `curated/`, `quarantine/`, `athena-results/`) | Separate S3 buckets per zone | A single versioned, encrypted bucket with prefix-scoped IAM policies and lifecycle rules avoids cross-bucket replication complexity while maintaining cryptographic and IAM separation between zones. |
| **Ingestion Compute** | AWS Lambda (`python3.12` on `arm64`) triggered by S3 `ObjectCreated` events | AWS Glue Spark ETL jobs or Amazon ECS tasks | Retail CSV batches (typically KB to tens of MB) process in milliseconds to seconds in Lambda at near-zero cost, whereas Glue Spark jobs incur a minimum DPU billing duration and cold-start latency. |
| **Partition Discovery** | Glue Catalog Table with **Athena Partition Projection** + on-demand Glue Crawler | Scheduled hourly Glue Crawler | Partition Projection computes `transaction_date=YYYY-MM-DD` locations mathematically at query time, making newly ingested files immediately queryable in Athena with zero crawler latency and zero DPU cost. The Glue Crawler remains provisioned on-demand for ad-hoc schema drift audits. |
| **Malformed Data Handling** | Row-level quarantine (`quarantine/transactions/rejected_rows/`) + file-level schema error reports (`quarantine/transactions/file_errors/`) | Dropping bad rows silently or failing entire batch on single bad row | Silent drops corrupt financial reporting; failing a 10,000-row file because of one malformed row blocks daily reporting. Splitting valid rows to `curated/` while writing rejected rows with deterministic error codes to `quarantine/` preserves both availability and auditability. |

---

## 2. Dual-Layer Recursive Processing Guard

A classic failure mode in event-driven S3 architectures occurs when a Lambda function triggered by an S3 bucket writes its output back into the same bucket, accidentally triggering itself in an infinite billing loop. This project implements two independent safeguards:

1. **Infrastructure Notification Filter (`terraform/modules/compute/main.tf`)**:
   The `aws_s3_bucket_notification` resource restricts `s3:ObjectCreated:*` events strictly to `filter_prefix = "raw/transactions/"` and `filter_suffix = ".csv"`. Objects written to `curated/transactions/`, `quarantine/transactions/`, or `athena-results/` never match the S3 notification rule.
2. **Application-Level Prefix Guard (`src/ingestion_lambda/validator.py`)**:
   Before reading any S3 object, `validate_object_key_against_recursive_trigger` verifies that the key starts with `raw/transactions/`, ends with `.csv`, and does not start with any protected output prefix (`curated/`, `quarantine/`, `athena-results/`). Any violation immediately raises `RecursiveTriggerGuardError` and logs a `RECURSIVE_TRIGGER_GUARD_BLOCKED` error event.

---

## 3. Least-Privilege IAM Permission Matrix

Each workload operates under a dedicated IAM principal scoped to exact S3 prefixes and service ARNs (`terraform/modules/iam/main.tf`):

| IAM Principal | Allowed S3 Read (`s3:GetObject`) | Allowed S3 Write (`s3:PutObject`) | Explicit Denies / Constraints |
| :--- | :--- | :--- | :--- |
| **`lambda-ingestion-role`** | `raw/transactions/*` only | `curated/transactions/*` and `quarantine/transactions/*` only | Cannot list bucket, delete objects, read `curated/`, or write to `raw/`. |
| **`glue-crawler-role`** | `curated/transactions/*` only | None (Read-only on S3) | `s3:ListBucket` conditioned on `s3:prefix = curated/transactions/*`. |
| **`athena-analyst-readonly`** | `curated/transactions/*` and `athena-results/*` | `athena-results/*` only (query staging) | Explicit `Deny` on `raw/transactions/*` (all actions) and `Deny` on `PutObject`/`DeleteObject` for `curated/` and `quarantine/`. |

---

## 4. Data Dictionary and Deterministic Validation Rules

### Raw Input Schema (`raw/transactions/*.csv`)

| Column | Type | Validation Rule | Error Code on Violation |
| :--- | :--- | :--- | :--- |
| `transaction_id` | String | Matches `^TXN-[A-Z0-9]{4,24}$` and unique within batch | `INVALID_TRANSACTION_ID`, `DUPLICATE_TRANSACTION_ID` |
| `transaction_timestamp` | ISO-8601 String | Valid ISO-8601 timestamp; normalized to UTC `YYYY-MM-DD HH:MM:SS` | `MISSING_TIMESTAMP`, `INVALID_TIMESTAMP` |
| `store_id` | String | Matches `^STORE-[0-9]{3,6}$` | `INVALID_STORE_ID` |
| `customer_id` | String | Matches `^CUST-[A-Z0-9]{4,16}$` or `GUEST` | `INVALID_CUSTOMER_ID` |
| `product_sku` | String | Matches `^SKU-[A-Z0-9-]{3,20}$` | `INVALID_PRODUCT_SKU` |
| `category` | String | Non-empty string up to 64 characters; normalized to Title Case | `INVALID_CATEGORY` |
| `quantity` | Integer | Positive integer in `[1, 10000]` | `INVALID_QUANTITY` |
| `unit_price` | Decimal(12,2) | Finite decimal `> 0.00` | `INVALID_UNIT_PRICE` |
| `discount_amount` | Decimal(12,2) | Finite decimal `>= 0.00` and `<= quantity * unit_price` | `NEGATIVE_DISCOUNT`, `INVALID_DISCOUNT_AMOUNT`, `DISCOUNT_EXCEEDS_GROSS_AMOUNT` |
| `payment_method` | String | One of `CARD`, `CASH`, `MOBILE_PAY`, `VOUCHER` | `UNSUPPORTED_PAYMENT_METHOD` |
| `currency` | String | One of `USD`, `EUR`, `GBP` | `UNSUPPORTED_CURRENCY` |

### Enriched Curated Columns (`curated/transactions/transaction_date=YYYY-MM-DD/*.csv`)

- `gross_amount`: Deterministically computed as $\text{round}(\text{quantity} \times \text{unit\_price}, 2)$.
- `net_amount`: Deterministically computed as $\text{round}(\text{gross\_amount} - \text{discount\_amount}, 2)$.
- `source_file`: S3 key of the originating raw CSV batch for end-to-end lineage.
- `ingested_at_utc`: ISO-8601 UTC timestamp of ingestion processing.
- `transaction_date`: Hive partition key (`YYYY-MM-DD`) derived from UTC-normalized `transaction_timestamp`.
