output "data_lake_bucket_name" {
  description = "S3 bucket name hosting raw, curated, quarantine, and Athena results prefixes"
  value       = module.storage.bucket_id
}

output "data_lake_bucket_arn" {
  description = "ARN of the S3 data lake bucket"
  value       = module.storage.bucket_arn
}

output "s3_prefix_layout" {
  description = "Canonical S3 prefix structure separating zones"
  value = {
    raw_incoming    = "s3://${module.storage.bucket_id}/${var.raw_prefix}"
    curated_zone    = "s3://${module.storage.bucket_id}/${var.curated_prefix}"
    quarantine_zone = "s3://${module.storage.bucket_id}/${var.quarantine_prefix}"
    athena_staging  = "s3://${module.storage.bucket_id}/${var.athena_results_prefix}"
  }
}

output "ingestion_lambda_function_name" {
  description = "Name of the event-triggered CSV validation Lambda function"
  value       = module.compute.lambda_function_name
}

output "ingestion_lambda_role_arn" {
  description = "ARN of the least-privilege IAM execution role for Lambda"
  value       = module.iam.lambda_role_arn
}

output "glue_catalog_database_name" {
  description = "Name of the AWS Glue Data Catalog database"
  value       = module.catalog_analytics.glue_database_name
}

output "glue_curated_table_name" {
  description = "Name of the partition-projected Glue Catalog table"
  value       = module.catalog_analytics.glue_table_name
}

output "glue_crawler_name" {
  description = "Name of the on-demand AWS Glue Crawler"
  value       = module.catalog_analytics.glue_crawler_name
}

output "athena_workgroup_name" {
  description = "Name of the cost-governed Amazon Athena workgroup"
  value       = module.catalog_analytics.athena_workgroup_name
}

output "athena_analyst_readonly_policy_arn" {
  description = "ARN of the least-privilege IAM policy for Athena SQL analysts"
  value       = module.iam.athena_analyst_policy_arn
}

output "cloudwatch_log_group_name" {
  description = "CloudWatch Log Group capturing structured JSON events from Lambda"
  value       = module.observability.lambda_log_group_name
}

output "ops_alerts_sns_topic_arn" {
  description = "SNS Topic ARN for CloudWatch invocation and quarantine alarms"
  value       = module.observability.ops_alerts_sns_topic_arn
}

output "configured_cloudwatch_alarms" {
  description = "List of active CloudWatch alarm names"
  value       = module.observability.alarm_names
}
