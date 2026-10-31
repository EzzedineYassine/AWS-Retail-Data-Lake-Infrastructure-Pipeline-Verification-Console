variable "name_prefix" {
  type        = string
  description = "Prefix used for naming IAM roles and policies"
}

variable "aws_region" {
  type        = string
  description = "AWS region for ARN construction"
}

variable "account_id" {
  type        = string
  description = "AWS account ID for least-privilege ARN scoping"
}

variable "bucket_arn" {
  type        = string
  description = "ARN of the S3 data lake bucket"
}

variable "raw_prefix" {
  type        = string
  description = "S3 prefix for incoming raw CSV objects"
}

variable "curated_prefix" {
  type        = string
  description = "S3 prefix for curated partitioned CSV objects"
}

variable "quarantine_prefix" {
  type        = string
  description = "S3 prefix for quarantined records"
}

variable "athena_results_prefix" {
  type        = string
  description = "S3 prefix for Athena query execution staging files"
}

variable "lambda_log_group_arn" {
  type        = string
  description = "ARN of the Lambda CloudWatch log group"
}

variable "glue_database_name" {
  type        = string
  description = "Name of the AWS Glue catalog database"
}

variable "athena_workgroup_name" {
  type        = string
  description = "Name of the Amazon Athena workgroup"
}

variable "tags" {
  type        = map(string)
  description = "Resource tags applied to IAM entities"
  default     = {}
}
