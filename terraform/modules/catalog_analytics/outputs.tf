output "glue_database_name" {
  description = "Name of the Glue catalog database"
  value       = aws_glue_catalog_database.retail_datalake.name
}

output "glue_table_name" {
  description = "Name of the curated transactions Glue table"
  value       = aws_glue_catalog_table.curated_transactions.name
}

output "glue_crawler_name" {
  description = "Name of the Glue crawler"
  value       = aws_glue_crawler.curated_transactions_crawler.name
}

output "athena_workgroup_name" {
  description = "Name of the Athena workgroup"
  value       = aws_athena_workgroup.retail_analytics.name
}

output "athena_named_query_ids" {
  description = "IDs of the pre-registered Athena named queries"
  value       = { for k, v in aws_athena_named_query.saved_queries : k => v.id }
}
