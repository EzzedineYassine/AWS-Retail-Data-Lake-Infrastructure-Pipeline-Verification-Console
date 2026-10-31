output "bucket_id" {
  description = "Name of the S3 data lake bucket"
  value       = aws_s3_bucket.datalake.id
}

output "bucket_arn" {
  description = "ARN of the S3 data lake bucket"
  value       = aws_s3_bucket.datalake.arn
}

output "bucket_domain_name" {
  description = "Bucket domain name"
  value       = aws_s3_bucket.datalake.bucket_domain_name
}
