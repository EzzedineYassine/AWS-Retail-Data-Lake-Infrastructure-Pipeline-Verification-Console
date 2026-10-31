output "lambda_function_name" {
  description = "Name of the deployed ingestion Lambda function"
  value       = aws_lambda_function.ingestion_processor.function_name
}

output "lambda_function_arn" {
  description = "ARN of the deployed ingestion Lambda function"
  value       = aws_lambda_function.ingestion_processor.arn
}

output "lambda_package_sha256" {
  description = "Base64 SHA256 digest of the packaged Lambda deployment archive"
  value       = data.archive_file.lambda_package.output_base64sha256
}
