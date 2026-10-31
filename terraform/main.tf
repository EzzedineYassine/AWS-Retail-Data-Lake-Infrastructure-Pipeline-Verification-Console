locals {
  name_prefix           = "${var.project_name}-${var.environment}"
  bucket_name           = "${var.project_name}-${var.environment}-${var.aws_account_id}"
  lambda_function_name  = "${local.name_prefix}-csv-ingestion"
  glue_database_name    = replace("${local.name_prefix}_db", "-", "_")
  glue_table_name       = "curated_transactions"
  glue_crawler_name     = "${local.name_prefix}-curated-crawler"
  athena_workgroup_name = "${local.name_prefix}-analytics-wg"
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
  saved_athena_queries = {
    "01_daily_store_revenue"           = file("${path.module}/../sql/01_daily_store_revenue.sql")
    "02_category_discount_performance" = file("${path.module}/../sql/02_category_discount_performance.sql")
    "03_payment_method_distribution"   = file("${path.module}/../sql/03_payment_method_distribution.sql")
    "04_hourly_basket_velocity"        = file("${path.module}/../sql/04_hourly_basket_velocity.sql")
    "05_ingestion_audit_summary"       = file("${path.module}/../sql/05_ingestion_audit_summary.sql")
  }
}

module "storage" {
  source = "./modules/storage"

  bucket_name           = local.bucket_name
  raw_prefix            = var.raw_prefix
  curated_prefix        = var.curated_prefix
  quarantine_prefix     = var.quarantine_prefix
  athena_results_prefix = var.athena_results_prefix
  force_destroy         = false
  tags                  = local.common_tags
}

module "observability" {
  source = "./modules/observability"

  name_prefix                    = local.name_prefix
  lambda_function_name           = local.lambda_function_name
  log_retention_days             = var.log_retention_days
  quarantine_row_alarm_threshold = var.quarantine_row_alarm_threshold
  alert_email                    = var.alert_email
  tags                           = local.common_tags
}

module "iam" {
  source = "./modules/iam"

  name_prefix           = local.name_prefix
  aws_region            = var.aws_region
  account_id            = var.aws_account_id
  bucket_arn            = module.storage.bucket_arn
  raw_prefix            = var.raw_prefix
  curated_prefix        = var.curated_prefix
  quarantine_prefix     = var.quarantine_prefix
  athena_results_prefix = var.athena_results_prefix
  lambda_log_group_arn  = module.observability.lambda_log_group_arn
  glue_database_name    = local.glue_database_name
  athena_workgroup_name = local.athena_workgroup_name
  tags                  = local.common_tags
}

module "compute" {
  source = "./modules/compute"

  function_name                  = local.lambda_function_name
  lambda_role_arn                = module.iam.lambda_role_arn
  bucket_id                      = module.storage.bucket_id
  bucket_arn                     = module.storage.bucket_arn
  account_id                     = var.aws_account_id
  raw_prefix                     = var.raw_prefix
  curated_prefix                 = var.curated_prefix
  quarantine_prefix              = var.quarantine_prefix
  source_root_dir                = "${path.module}/../src"
  build_output_path              = "${path.module}/build/ingestion_lambda.zip"
  memory_size_mb                 = var.lambda_memory_size_mb
  timeout_seconds                = var.lambda_timeout_seconds
  reserved_concurrent_executions = var.lambda_reserved_concurrency
  tags                           = local.common_tags
}

module "catalog_analytics" {
  source = "./modules/catalog_analytics"

  database_name               = local.glue_database_name
  table_name                  = local.glue_table_name
  crawler_name                = local.glue_crawler_name
  glue_crawler_role_arn       = module.iam.glue_crawler_role_arn
  workgroup_name              = local.athena_workgroup_name
  bucket_id                   = module.storage.bucket_id
  curated_prefix              = var.curated_prefix
  athena_results_prefix       = var.athena_results_prefix
  athena_bytes_scanned_cutoff = var.athena_bytes_scanned_cutoff
  named_queries               = local.saved_athena_queries
  tags                        = local.common_tags
}
