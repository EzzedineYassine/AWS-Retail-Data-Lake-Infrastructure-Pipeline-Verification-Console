variable "bucket_name" {
  type        = string
  description = "Globally unique name for the retail data lake S3 bucket"
}

variable "raw_prefix" {
  type        = string
  description = "S3 key prefix for incoming raw retail CSV files"
  default     = "raw/transactions/"
}

variable "curated_prefix" {
  type        = string
  description = "S3 key prefix for validated and partitioned curated datasets"
  default     = "curated/transactions/"
}

variable "quarantine_prefix" {
  type        = string
  description = "S3 key prefix for rejected rows and schema validation failure reports"
  default     = "quarantine/transactions/"
}

variable "athena_results_prefix" {
  type        = string
  description = "S3 key prefix for Amazon Athena workgroup query outputs"
  default     = "athena-results/"
}

variable "quarantine_retention_days" {
  type        = number
  description = "Number of days to retain quarantined records before automatic expiration"
  default     = 90
}

variable "athena_results_retention_days" {
  type        = number
  description = "Number of days to retain Athena query staging files before expiration"
  default     = 7
}

variable "force_destroy" {
  type        = bool
  description = "Whether to allow bucket deletion when objects exist"
  default     = false
}

variable "tags" {
  type        = map(string)
  description = "Resource tags applied to storage infrastructure"
  default     = {}
}
