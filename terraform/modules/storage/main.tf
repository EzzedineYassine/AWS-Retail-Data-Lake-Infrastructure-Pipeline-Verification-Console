resource "aws_s3_bucket" "datalake" {
  bucket        = var.bucket_name
  force_destroy = var.force_destroy
  tags          = var.tags
}

resource "aws_s3_bucket_ownership_controls" "datalake" {
  bucket = aws_s3_bucket.datalake.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "datalake" {
  bucket = aws_s3_bucket.datalake.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "datalake" {
  bucket = aws_s3_bucket.datalake.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "datalake" {
  bucket = aws_s3_bucket.datalake.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "datalake" {
  bucket = aws_s3_bucket.datalake.id

  depends_on = [aws_s3_bucket_versioning.datalake]

  rule {
    id     = "raw-data-tiering-and-noncurrent-cleanup"
    status = "Enabled"

    filter {
      prefix = var.raw_prefix
    }

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER_IR"
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }

  rule {
    id     = "curated-data-noncurrent-version-cleanup"
    status = "Enabled"

    filter {
      prefix = var.curated_prefix
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }

  rule {
    id     = "quarantine-records-retention"
    status = "Enabled"

    filter {
      prefix = var.quarantine_prefix
    }

    expiration {
      days = var.quarantine_retention_days
    }

    noncurrent_version_expiration {
      noncurrent_days = 14
    }
  }

  rule {
    id     = "athena-query-results-cleanup"
    status = "Enabled"

    filter {
      prefix = var.athena_results_prefix
    }

    expiration {
      days = var.athena_results_retention_days
    }

    noncurrent_version_expiration {
      noncurrent_days = 3
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

data "aws_iam_policy_document" "enforce_tls_only" {
  statement {
    sid    = "DenyInsecureTransport"
    effect = "Deny"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions = ["s3:*"]

    resources = [
      aws_s3_bucket.datalake.arn,
      "${aws_s3_bucket.datalake.arn}/*",
    ]

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "datalake_tls" {
  bucket = aws_s3_bucket.datalake.id
  policy = data.aws_iam_policy_document.enforce_tls_only.json

  depends_on = [aws_s3_bucket_public_access_block.datalake]
}
