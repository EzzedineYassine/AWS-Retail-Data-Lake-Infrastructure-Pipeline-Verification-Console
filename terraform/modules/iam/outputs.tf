output "lambda_role_arn" {
  description = "ARN of the Lambda ingestion IAM role"
  value       = aws_iam_role.lambda_ingestion.arn
}

output "lambda_role_name" {
  description = "Name of the Lambda ingestion IAM role"
  value       = aws_iam_role.lambda_ingestion.name
}

output "glue_crawler_role_arn" {
  description = "ARN of the Glue crawler IAM role"
  value       = aws_iam_role.glue_crawler.arn
}

output "athena_analyst_policy_arn" {
  description = "ARN of the read-only Athena analyst IAM policy"
  value       = aws_iam_policy.athena_analyst_readonly.arn
}
