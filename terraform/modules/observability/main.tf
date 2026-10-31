resource "aws_cloudwatch_log_group" "lambda_ingestion" {
  name              = "/aws/lambda/${var.lambda_function_name}"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

resource "aws_sns_topic" "ops_alerts" {
  name = "${var.name_prefix}-ops-alerts"
  tags = var.tags
}

resource "aws_sns_topic_subscription" "email_alert" {
  count     = length(trimspace(var.alert_email)) > 0 ? 1 : 0
  topic_arn = aws_sns_topic.ops_alerts.arn
  protocol  = "email"
  endpoint  = trimspace(var.alert_email)
}

resource "aws_cloudwatch_log_metric_filter" "quarantine_rows" {
  name           = "${var.name_prefix}-quarantine-rows-filter"
  pattern        = "{ $.event_type = \"QUARANTINE_ROWS_DETECTED\" }"
  log_group_name = aws_cloudwatch_log_group.lambda_ingestion.name

  metric_transformation {
    name          = "QuarantinedRowCount"
    namespace     = "RetailDataLake/Ingestion"
    value         = "$.quarantined_row_count"
    default_value = "0"
  }
}

resource "aws_cloudwatch_log_metric_filter" "schema_validation_failure" {
  name           = "${var.name_prefix}-schema-validation-failure-filter"
  pattern        = "{ $.event_type = \"FILE_VALIDATION_FAILURE\" }"
  log_group_name = aws_cloudwatch_log_group.lambda_ingestion.name

  metric_transformation {
    name          = "SchemaValidationFailures"
    namespace     = "RetailDataLake/Ingestion"
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_metric_alarm" "lambda_invocation_errors" {
  alarm_name          = "${var.name_prefix}-lambda-invocation-errors"
  alarm_description   = "Triggers when the retail CSV ingestion Lambda function fails with an unhandled error or schema rejection"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 1
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = var.lambda_function_name
  }

  alarm_actions = [aws_sns_topic.ops_alerts.arn]
  ok_actions    = [aws_sns_topic.ops_alerts.arn]
  tags          = var.tags
}

resource "aws_cloudwatch_metric_alarm" "lambda_throttles" {
  alarm_name          = "${var.name_prefix}-lambda-throttles"
  alarm_description   = "Triggers when the retail CSV ingestion Lambda function hits concurrency throttling"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "Throttles"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 1
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = var.lambda_function_name
  }

  alarm_actions = [aws_sns_topic.ops_alerts.arn]
  tags          = var.tags
}

resource "aws_cloudwatch_metric_alarm" "quarantined_rows_threshold" {
  alarm_name          = "${var.name_prefix}-quarantined-rows-spike"
  alarm_description   = "Triggers when quarantined rows exceed threshold within a 5-minute ingestion window"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "QuarantinedRowCount"
  namespace           = "RetailDataLake/Ingestion"
  period              = 300
  statistic           = "Sum"
  threshold           = var.quarantine_row_alarm_threshold
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.ops_alerts.arn]
  tags          = var.tags
}
