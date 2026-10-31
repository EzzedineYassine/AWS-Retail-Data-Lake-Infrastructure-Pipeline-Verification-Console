data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    sid     = "AllowLambdaServiceAssumeRole"
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda_ingestion" {
  name               = "${var.name_prefix}-lambda-ingestion-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
  tags               = var.tags
}

data "aws_iam_policy_document" "lambda_least_privilege" {
  statement {
    sid    = "ReadRawRetailCsvObjectsOnly"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:GetObjectVersion",
    ]
    resources = [
      "${var.bucket_arn}/${var.raw_prefix}*",
    ]
  }

  statement {
    sid    = "WriteCuratedAndQuarantineObjectsOnly"
    effect = "Allow"
    actions = [
      "s3:PutObject",
    ]
    resources = [
      "${var.bucket_arn}/${var.curated_prefix}*",
      "${var.bucket_arn}/${var.quarantine_prefix}*",
    ]
  }

  statement {
    sid    = "WriteStructuredCloudWatchLogs"
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = [
      "${var.lambda_log_group_arn}:*",
    ]
  }
}

resource "aws_iam_role_policy" "lambda_least_privilege" {
  name   = "${var.name_prefix}-lambda-s3-cw-policy"
  role   = aws_iam_role.lambda_ingestion.id
  policy = data.aws_iam_policy_document.lambda_least_privilege.json
}

data "aws_iam_policy_document" "glue_assume_role" {
  statement {
    sid     = "AllowGlueServiceAssumeRole"
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["glue.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "glue_crawler" {
  name               = "${var.name_prefix}-glue-crawler-role"
  assume_role_policy = data.aws_iam_policy_document.glue_assume_role.json
  tags               = var.tags
}

data "aws_iam_policy_document" "glue_crawler_least_privilege" {
  statement {
    sid    = "ListCuratedPrefixOnly"
    effect = "Allow"
    actions = [
      "s3:ListBucket",
    ]
    resources = [
      var.bucket_arn,
    ]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["${var.curated_prefix}*"]
    }
  }

  statement {
    sid    = "ReadCuratedObjectsOnly"
    effect = "Allow"
    actions = [
      "s3:GetObject",
    ]
    resources = [
      "${var.bucket_arn}/${var.curated_prefix}*",
    ]
  }

  statement {
    sid    = "ManageRetailGlueCatalogMetadata"
    effect = "Allow"
    actions = [
      "glue:GetDatabase",
      "glue:GetTable",
      "glue:GetTables",
      "glue:CreateTable",
      "glue:UpdateTable",
      "glue:GetPartition",
      "glue:GetPartitions",
      "glue:CreatePartition",
      "glue:BatchCreatePartition",
      "glue:UpdatePartition",
      "glue:BatchGetPartition",
    ]
    resources = [
      "arn:aws:glue:${var.aws_region}:${var.account_id}:catalog",
      "arn:aws:glue:${var.aws_region}:${var.account_id}:database/${var.glue_database_name}",
      "arn:aws:glue:${var.aws_region}:${var.account_id}:table/${var.glue_database_name}/*",
    ]
  }

  statement {
    sid    = "WriteCrawlerLogs"
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = [
      "arn:aws:logs:${var.aws_region}:${var.account_id}:log-group:/aws-glue/crawlers*",
    ]
  }
}

resource "aws_iam_role_policy" "glue_crawler_least_privilege" {
  name   = "${var.name_prefix}-glue-crawler-policy"
  role   = aws_iam_role.glue_crawler.id
  policy = data.aws_iam_policy_document.glue_crawler_least_privilege.json
}

data "aws_iam_policy_document" "athena_analyst_readonly" {
  statement {
    sid    = "ExecuteQueriesInRetailWorkgroup"
    effect = "Allow"
    actions = [
      "athena:StartQueryExecution",
      "athena:StopQueryExecution",
      "athena:GetQueryExecution",
      "athena:GetQueryResults",
      "athena:GetWorkGroup",
      "athena:ListNamedQueries",
      "athena:GetNamedQuery",
    ]
    resources = [
      "arn:aws:athena:${var.aws_region}:${var.account_id}:workgroup/${var.athena_workgroup_name}",
    ]
  }

  statement {
    sid    = "ReadGlueCatalogMetadata"
    effect = "Allow"
    actions = [
      "glue:GetDatabase",
      "glue:GetTable",
      "glue:GetTables",
      "glue:GetPartition",
      "glue:GetPartitions",
    ]
    resources = [
      "arn:aws:glue:${var.aws_region}:${var.account_id}:catalog",
      "arn:aws:glue:${var.aws_region}:${var.account_id}:database/${var.glue_database_name}",
      "arn:aws:glue:${var.aws_region}:${var.account_id}:table/${var.glue_database_name}/*",
    ]
  }

  statement {
    sid    = "ReadCuratedZoneObjects"
    effect = "Allow"
    actions = [
      "s3:GetObject",
    ]
    resources = [
      "${var.bucket_arn}/${var.curated_prefix}*",
    ]
  }

  statement {
    sid    = "ListDataLakeBucketForAthena"
    effect = "Allow"
    actions = [
      "s3:GetBucketLocation",
      "s3:ListBucket",
    ]
    resources = [
      var.bucket_arn,
    ]
  }

  statement {
    sid    = "ReadWriteAthenaQueryStagingResults"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:AbortMultipartUpload",
    ]
    resources = [
      "${var.bucket_arn}/${var.athena_results_prefix}*",
    ]
  }

  statement {
    sid    = "DenyAccessToRawZoneAndMutationOfCuratedZone"
    effect = "Deny"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
    ]
    resources = [
      "${var.bucket_arn}/${var.raw_prefix}*",
    ]
  }

  statement {
    sid    = "DenyMutationOfCuratedAndQuarantineZones"
    effect = "Deny"
    actions = [
      "s3:PutObject",
      "s3:DeleteObject",
    ]
    resources = [
      "${var.bucket_arn}/${var.curated_prefix}*",
      "${var.bucket_arn}/${var.quarantine_prefix}*",
    ]
  }
}

resource "aws_iam_policy" "athena_analyst_readonly" {
  name        = "${var.name_prefix}-athena-analyst-readonly"
  description = "Least-privilege policy allowing SQL analytics in Athena over curated retail data only"
  policy      = data.aws_iam_policy_document.athena_analyst_readonly.json
  tags        = var.tags
}
