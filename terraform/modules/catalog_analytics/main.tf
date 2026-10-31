resource "aws_glue_catalog_database" "retail_datalake" {
  name        = var.database_name
  description = "Retail data lake analytics catalog for validated point-of-sale transactions"
}

resource "aws_glue_catalog_table" "curated_transactions" {
  name          = var.table_name
  database_name = aws_glue_catalog_database.retail_datalake.name
  table_type    = "EXTERNAL_TABLE"

  parameters = {
    "EXTERNAL"                             = "TRUE"
    "classification"                       = "csv"
    "skip.header.line.count"               = "1"
    "projection.enabled"                   = "true"
    "projection.transaction_date.type"     = "date"
    "projection.transaction_date.format"   = "yyyy-MM-dd"
    "projection.transaction_date.range"    = "2024-01-01,NOW"
    "projection.transaction_date.interval" = "1"
    "storage.location.template"            = "s3://${var.bucket_id}/${var.curated_prefix}transaction_date=$${transaction_date}"
  }

  partition_keys {
    name = "transaction_date"
    type = "string"
  }

  storage_descriptor {
    location      = "s3://${var.bucket_id}/${var.curated_prefix}"
    input_format  = "org.apache.hadoop.mapred.TextInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat"

    ser_de_info {
      name                  = "OpenCSVSerde"
      serialization_library = "org.apache.hadoop.hive.serde2.OpenCSVSerde"

      parameters = {
        "separatorChar" = ","
        "quoteChar"     = "\""
        "escapeChar"    = "\\"
      }
    }

    columns {
      name = "transaction_id"
      type = "string"
    }

    columns {
      name = "transaction_timestamp"
      type = "string"
    }

    columns {
      name = "store_id"
      type = "string"
    }

    columns {
      name = "customer_id"
      type = "string"
    }

    columns {
      name = "product_sku"
      type = "string"
    }

    columns {
      name = "category"
      type = "string"
    }

    columns {
      name = "quantity"
      type = "int"
    }

    columns {
      name = "unit_price"
      type = "decimal(12,2)"
    }

    columns {
      name = "discount_amount"
      type = "decimal(12,2)"
    }

    columns {
      name = "gross_amount"
      type = "decimal(12,2)"
    }

    columns {
      name = "net_amount"
      type = "decimal(12,2)"
    }

    columns {
      name = "payment_method"
      type = "string"
    }

    columns {
      name = "currency"
      type = "string"
    }

    columns {
      name = "source_file"
      type = "string"
    }

    columns {
      name = "ingested_at_utc"
      type = "string"
    }
  }
}

resource "aws_glue_crawler" "curated_transactions_crawler" {
  name          = var.crawler_name
  database_name = aws_glue_catalog_database.retail_datalake.name
  role          = var.glue_crawler_role_arn
  description   = "On-demand crawler over curated retail transactions prefix"
  table_prefix  = "crawler_"

  s3_target {
    path = "s3://${var.bucket_id}/${var.curated_prefix}"
  }

  schema_change_policy {
    delete_behavior = "LOG"
    update_behavior = "LOG"
  }

  tags = var.tags
}

resource "aws_athena_workgroup" "retail_analytics" {
  name        = var.workgroup_name
  description = "Cost-governed Athena workgroup for retail data lake SQL analytics"
  state       = "ENABLED"

  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true
    bytes_scanned_cutoff_per_query     = var.athena_bytes_scanned_cutoff

    result_configuration {
      output_location = "s3://${var.bucket_id}/${var.athena_results_prefix}"

      encryption_configuration {
        encryption_option = "SSE_S3"
      }
    }
  }

  tags = var.tags
}

resource "aws_athena_named_query" "saved_queries" {
  for_each = var.named_queries

  name        = each.key
  workgroup   = aws_athena_workgroup.retail_analytics.id
  database    = aws_glue_catalog_database.retail_datalake.name
  description = "Saved analytical query: ${each.key}"
  query       = each.value
}
