from pathlib import Path
import shutil
import subprocess

from scripts.validate_pipeline import run_validation_pipeline

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_end_to_end_pipeline_and_athena_sql_queries() -> None:
    summary = run_validation_pipeline()
    assert summary["batches_processed"] == 2
    assert summary["total_curated_rows_loaded"] == 20
    assert summary["total_quarantined_rows"] == 6
    assert summary["schema_error_caught"] is True
    assert summary["recursive_guard_verified"] is True
    assert len(summary["athena_queries_executed"]) == 5
    assert Path(summary["inspector_html"]).exists()


def test_terraform_modules_define_required_security_and_analytics_resources() -> None:
    tf_root = PROJECT_ROOT / "terraform"
    all_tf_text = "\n".join(
        p.read_text(encoding="utf-8") for p in tf_root.rglob("*.tf")
    )

    required_resources = [
        'resource "aws_s3_bucket" "datalake"',
        'resource "aws_s3_bucket_public_access_block" "datalake"',
        'resource "aws_s3_bucket_server_side_encryption_configuration" "datalake"',
        'resource "aws_s3_bucket_versioning" "datalake"',
        'resource "aws_s3_bucket_lifecycle_configuration" "datalake"',
        'resource "aws_s3_bucket_policy" "datalake_tls"',
        'resource "aws_lambda_function" "ingestion_processor"',
        'resource "aws_s3_bucket_notification" "raw_csv_trigger"',
        'resource "aws_glue_catalog_database" "retail_datalake"',
        'resource "aws_glue_catalog_table" "curated_transactions"',
        'resource "aws_glue_crawler" "curated_transactions_crawler"',
        'resource "aws_athena_workgroup" "retail_analytics"',
        'resource "aws_athena_named_query" "saved_queries"',
        'resource "aws_cloudwatch_log_group" "lambda_ingestion"',
        'resource "aws_cloudwatch_metric_alarm" "lambda_invocation_errors"',
        'resource "aws_cloudwatch_metric_alarm" "quarantined_rows_threshold"',
        'resource "aws_iam_role" "lambda_ingestion"',
        'resource "aws_iam_policy" "athena_analyst_readonly"',
    ]
    for resource_decl in required_resources:
        assert resource_decl in all_tf_text, f"Missing Terraform resource: {resource_decl}"


def test_terraform_fmt_and_validate_pass() -> None:
    tf_binary = shutil.which("terraform")
    if not tf_binary:
        return
    fmt_result = subprocess.run(
        [tf_binary, "fmt", "-check", "-recursive"],
        cwd=str(PROJECT_ROOT / "terraform"),
        capture_output=True,
        text=True,
        check=False,
    )
    assert fmt_result.returncode == 0, (
        f"terraform fmt failed: {fmt_result.stdout} {fmt_result.stderr}"
    )

    val_result = subprocess.run(
        [tf_binary, "validate"],
        cwd=str(PROJECT_ROOT / "terraform"),
        capture_output=True,
        text=True,
        check=False,
    )
    assert val_result.returncode == 0, (
        f"terraform validate failed: {val_result.stdout} {val_result.stderr}"
    )
