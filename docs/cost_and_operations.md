# Cost Governance and Operational Runbook

## 1. AWS Service Cost Model and Guardrails

Even serverless architectures can incur unexpected charges if log retention, query scan limits, or storage lifecycles are left unbounded. The table below summarizes the cost drivers for each AWS service in this architecture and the built-in Terraform guardrails that control spend.

| AWS Service | Primary Billing Dimension | Built-in Terraform Cost Guardrail | Estimated Monthly Cost (Small Retailer: ~5 GB/mo, 1,000 files/mo, 200 queries/mo) |
| :--- | :--- | :--- | :--- |
| **Amazon S3** | GB-month stored + `PUT`/`GET` requests | Lifecycle rules transition `raw/` to `STANDARD_IA` (30d) and `GLACIER_IR` (90d), expire noncurrent versions after 30d, expire `quarantine/` after 90d, and expire `athena-results/` after 7d. S3 Bucket Keys enabled. | **< $0.50 / month** |
| **AWS Lambda** | Invocation count + GB-seconds (`arm64`) | Graviton2 (`arm64`) runtime, 256 MB memory, 60s timeout, `reserved_concurrent_executions = 10`, and `maximum_retry_attempts = 1` on failed events. Covered by AWS Free Tier (1M requests + 400,000 GB-sec/mo). | **$0.00 / month** (within Free Tier) |
| **AWS Glue Data Catalog** | Objects stored (> 1M) + Crawler DPU-hours ($0.44/DPU-hr) | Uses **Athena Partition Projection** so daily partitions require zero Crawler runs. Crawler is provisioned on-demand (unscheduled) to avoid recurring DPU charges. | **$0.00 / month** (under 1M objects, 0 scheduled Crawler DPUs) |
| **Amazon Athena** | $5.00 per TB of data scanned | Hive partitioning by `transaction_date` + `bytes_scanned_cutoff_per_query = 10737418240` (10 GB hard ceiling per query) enforced at the workgroup level. | **< $0.25 / month** |
| **Amazon CloudWatch & SNS** | Log ingestion ($0.50/GB), storage, and custom metric alarms ($0.10/alarm/mo) | Explicit `retention_in_days = 30` on `/aws/lambda/...` log group and 3 targeted metric alarms (`Errors`, `Throttles`, `QuarantinedRowCount`). | **~$0.30 – $1.00 / month** |

---

## 2. Investigating Unsuccessful Processing (Operational Runbook)

When a malformed file or defective row arrives in `s3://<bucket>/raw/transactions/`, operators have three complementary ways to investigate the issue:

### A. CloudWatch Logs Insights Queries

All Lambda logs are emitted as structured single-line JSON payloads. Run the following query in CloudWatch Logs Insights against `/aws/lambda/retail-datalake-dev-csv-ingestion`:

```
fields timestamp_utc, level, event_type, batch_id, source_key, quarantined_row_count, quarantine_key, error_message
| filter event_type in ["QUARANTINE_ROWS_DETECTED", "FILE_VALIDATION_FAILURE", "RECURSIVE_TRIGGER_GUARD_BLOCKED"]
| sort timestamp_utc desc
| limit 50
```

### B. Inspecting Row-Level Quarantine Payloads in S3

When individual rows fail validation while the rest of the CSV batch succeeds, the valid rows are written to `curated/transactions/` and a diagnostic JSON report is written to:

`s3://<bucket>/quarantine/transactions/rejected_rows/ingestion_date=YYYY-MM-DD/<batch_id>_rejected.json`

Each report contains:
- `summary.error_code_breakdown`: Exact counts per error code (e.g., `INVALID_QUANTITY`, `DISCOUNT_EXCEEDS_GROSS_AMOUNT`, `DUPLICATE_TRANSACTION_ID`).
- `rejected_rows`: Array of rejected records with 1-based CSV `row_number`, `error_codes`, human-readable `error_messages`, and the sanitized `raw_row` dictionary.

### C. Inspecting File-Level Schema Rejections in S3

When an uploaded CSV is missing required headers (such as `unit_price` or `currency`), no curated partitions are written. Instead:
1. A diagnostic JSON report is saved to `s3://<bucket>/quarantine/transactions/file_errors/ingestion_date=YYYY-MM-DD/<batch_id>_schema_error.json`.
2. A `FILE_VALIDATION_FAILURE` JSON error log is emitted, incrementing the `RetailDataLake/Ingestion::SchemaValidationFailures` metric.
3. The Lambda invocation raises `SchemaValidationError`, triggering the CloudWatch `lambda-invocation-errors` alarm and notifying the SNS operations topic.
