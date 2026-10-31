variable "database_name" {
  type        = string
  description = "Name of the AWS Glue Data Catalog database"
}

variable "table_name" {
  type        = string
  description = "Name of the curated transactions Glue table"
  default     = "curated_transactions"
}

variable "crawler_name" {
  type        = string
  description = "Name of the AWS Glue Crawler for curated data"
}

variable "glue_crawler_role_arn" {
  type        = string
  description = "IAM role ARN assumed by the AWS Glue Crawler"
}

variable "workgroup_name" {
  type        = string
  description = "Name of the Amazon Athena analytics workgroup"
}

variable "bucket_id" {
  type        = string
  description = "Name of the S3 data lake bucket"
}

variable "curated_prefix" {
  type        = string
  description = "S3 prefix containing Hive-partitioned curated CSV files"
}

variable "athena_results_prefix" {
  type        = string
  description = "S3 prefix where Athena stores query execution outputs"
}

variable "athena_bytes_scanned_cutoff" {
  type        = number
  description = "Maximum bytes a single Athena query may scan before termination"
  default     = 10737418240
}

variable "named_queries" {
  type        = map(string)
  description = "Map of query name to SQL query text registered in the Athena workgroup"
  default     = {}
}

variable "tags" {
  type        = map(string)
  description = "Resource tags applied to catalog and analytics resources"
  default     = {}
}
