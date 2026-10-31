data "archive_file" "lambda_package" {
  type        = "zip"
  source_dir  = var.source_root_dir
  output_path = var.build_output_path
  excludes = [
    "__pycache__",
    "*.pyc",
    "*.pyo",
  ]
}

resource "aws_lambda_function" "ingestion_processor" {
  function_name                  = var.function_name
  description                    = "Validates incoming retail CSV files from raw prefix and writes partitioned curated data or quarantine diagnostics"
  role                           = var.lambda_role_arn
  handler                        = "ingestion_lambda.handler.lambda_handler"
  runtime                        = "python3.12"
  architectures                  = ["arm64"]
  filename                       = data.archive_file.lambda_package.output_path
  source_code_hash               = data.archive_file.lambda_package.output_base64sha256
  memory_size                    = var.memory_size_mb
  timeout                        = var.timeout_seconds
  reserved_concurrent_executions = var.reserved_concurrent_executions

  environment {
    variables = {
      DATA_LAKE_BUCKET        = var.bucket_id
      RAW_PREFIX              = var.raw_prefix
      CURATED_PREFIX          = var.curated_prefix
      QUARANTINE_PREFIX       = var.quarantine_prefix
      EXPECTED_SCHEMA_VERSION = "1.0"
      LOG_LEVEL               = var.log_level
    }
  }

  tags = var.tags
}

resource "aws_lambda_function_event_invoke_config" "ingestion_retry_policy" {
  function_name                = aws_lambda_function.ingestion_processor.function_name
  maximum_event_age_in_seconds = 3600
  maximum_retry_attempts       = 1
}

resource "aws_lambda_permission" "allow_s3_raw_notification" {
  statement_id   = "AllowExecutionFromS3RawCsvEvents"
  action         = "lambda:InvokeFunction"
  function_name  = aws_lambda_function.ingestion_processor.function_name
  principal      = "s3.amazonaws.com"
  source_arn     = var.bucket_arn
  source_account = var.account_id
}

resource "aws_s3_bucket_notification" "raw_csv_trigger" {
  bucket = var.bucket_id

  lambda_function {
    id                  = "trigger-retail-csv-validator-on-raw-prefix"
    lambda_function_arn = aws_lambda_function.ingestion_processor.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = var.raw_prefix
    filter_suffix       = ".csv"
  }

  depends_on = [aws_lambda_permission.allow_s3_raw_notification]
}
