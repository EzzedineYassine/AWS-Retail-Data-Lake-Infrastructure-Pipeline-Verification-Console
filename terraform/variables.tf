variable "project_name" {
  type        = string
  description = "Short identifier for the retail data lake project"
  default     = "retail-datalake"

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.project_name))
    error_message = "project_name must contain only lowercase alphanumeric characters and hyphens."
  }
}

variable "environment" {
  type        = string
  description = "Deployment environment name"
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

variable "aws_region" {
  type        = string
  description = "Target AWS region for all data lake resources"
  default     = "us-east-1"
}

variable "aws_account_id" {
  type        = string
  description = "12-digit AWS account ID used for least-privilege ARN scoping and unique S3 bucket naming"
  default     = "123456789012"

  validation {
    condition     = can(regex("^[0-9]{12}$", var.aws_account_id))
    error_message = "aws_account_id must be a 12-digit numeric AWS account identifier."
  }
}

variable "raw_prefix" {
  type        = string
  description = "S3 prefix for incoming raw retail CSV files"
  default     = "raw/transactions/"
}

variable "curated_prefix" {
  type        = string
  description = "S3 prefix for validated Hive-partitioned CSV files"
  default     = "curated/transactions/"
}

variable "quarantine_prefix" {
  type        = string
  description = "S3 prefix for rejected rows and schema validation failure diagnostics"
  default     = "quarantine/transactions/"
}

variable "athena_results_prefix" {
  type        = string
  description = "S3 prefix for Athena workgroup query outputs"
  default     = "athena-results/"
}

variable "lambda_memory_size_mb" {
  type        = number
  description = "Memory allocated to the CSV ingestion Lambda function in MB"
  default     = 256
}

variable "lambda_timeout_seconds" {
  type        = number
  description = "Timeout for the CSV ingestion Lambda function in seconds"
  default     = 60
}

variable "lambda_reserved_concurrency" {
  type        = number
  description = "Reserved concurrency ceiling for the ingestion Lambda function"
  default     = 10
}

variable "athena_bytes_scanned_cutoff" {
  type        = number
  description = "Per-query byte scan limit in Athena to prevent unexpected query costs"
  default     = 10737418240
}

variable "log_retention_days" {
  type        = number
  description = "Retention period in days for CloudWatch log groups"
  default     = 30
}

variable "quarantine_row_alarm_threshold" {
  type        = number
  description = "Quarantined row count within 5 minutes that triggers an SNS alert"
  default     = 10
}

variable "alert_email" {
  type        = string
  description = "Optional operator email address for CloudWatch alarm notifications"
  default     = ""
}
