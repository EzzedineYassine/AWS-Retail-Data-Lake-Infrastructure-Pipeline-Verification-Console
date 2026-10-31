output "lambda_log_group_name" {
  description = "Name of the CloudWatch log group for Lambda"
  value       = aws_cloudwatch_log_group.lambda_ingestion.name
}

output "lambda_log_group_arn" {
  description = "ARN of the CloudWatch log group for Lambda"
  value       = aws_cloudwatch_log_group.lambda_ingestion.arn
}

output "ops_alerts_sns_topic_arn" {
  description = "ARN of the SNS topic receiving operational alarms"
  value       = aws_sns_topic.ops_alerts.arn
}

output "alarm_names" {
  description = "Names of the configured CloudWatch metric alarms"
  value = [
    aws_cloudwatch_metric_alarm.lambda_invocation_errors.alarm_name,
    aws_cloudwatch_metric_alarm.lambda_throttles.alarm_name,
    aws_cloudwatch_metric_alarm.quarantined_rows_threshold.alarm_name,
  ]
}
