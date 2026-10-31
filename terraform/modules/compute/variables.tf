variable "function_name" {
  type        = string
  description = "Name of the retail CSV ingestion Lambda function"
}

variable "lambda_role_arn" {
  type        = string
  description = "IAM execution role ARN for the Lambda function"
}

variable "bucket_id" {
  type        = string
  description = "S3 data lake bucket name"
}

variable "bucket_arn" {
  type        = string
  description = "S3 data lake bucket ARN"
}

variable "account_id" {
  type        = string
  description = "AWS account ID for S3 event permission scoping"
}

variable "raw_prefix" {
  type        = string
  description = "S3 key prefix that triggers the ingestion Lambda"
}

variable "curated_prefix" {
  type        = string
  description = "S3 key prefix where validated partitions are written"
}

variable "quarantine_prefix" {
  type        = string
  description = "S3 key prefix where rejected records are written"
}

variable "source_root_dir" {
  type        = string
  description = "Filesystem path containing the Python source package"
}

variable "build_output_path" {
  type        = string
  description = "Filesystem path where the packaged Lambda zip will be created"
}

variable "memory_size_mb" {
  type        = number
  description = "Memory allocated to the Lambda function in MB"
  default     = 256
}

variable "timeout_seconds" {
  type        = number
  description = "Execution timeout for the Lambda function in seconds"
  default     = 60
}

variable "reserved_concurrent_executions" {
  type        = number
  description = "Reserved concurrency limit to protect downstream resources and costs"
  default     = 10
}

variable "log_level" {
  type        = string
  description = "Application log verbosity level"
  default     = "INFO"
}

variable "tags" {
  type        = map(string)
  description = "Resource tags applied to compute infrastructure"
  default     = {}
}
