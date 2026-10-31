variable "name_prefix" {
  type        = string
  description = "Resource naming prefix for observability components"
}

variable "lambda_function_name" {
  type        = string
  description = "Name of the Lambda function to monitor"
}

variable "log_retention_days" {
  type        = number
  description = "Number of days to retain CloudWatch logs"
  default     = 30
}

variable "quarantine_row_alarm_threshold" {
  type        = number
  description = "Threshold of quarantined rows within 5 minutes that triggers a data quality alarm"
  default     = 10
}

variable "alert_email" {
  type        = string
  description = "Optional email address to subscribe to operational SNS alerts"
  default     = ""
}

variable "tags" {
  type        = map(string)
  description = "Resource tags applied to observability infrastructure"
  default     = {}
}
