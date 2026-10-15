# Serverless orders pipeline:
#   input S3 bucket --(ObjectCreated *.csv)--> Lambda (container) --> output S3 bucket
#
# Apply order matters on the FIRST deploy: the Lambda needs an image in ECR, so
# create the ECR repo first (-target=module.ecr_repo), push an image, then apply
# everything. See the top-level readme.md.

# ---------------------------------------------------------------------------
# S3 buckets
# ---------------------------------------------------------------------------
resource "aws_s3_bucket" "input_s3" {
  bucket = "${local.app_name}-input-bucket"
  tags = merge({
    Name        = "${local.app_name}-input-bucket"
    Environment = "${var.env}"
    }, local.default_tags
  )
  force_destroy = true
}

resource "aws_s3_bucket" "output_s3" {
  bucket = "${local.app_name}-output-bucket"
  tags = merge({
    Name        = "${local.app_name}-output-bucket"
    Environment = "${var.env}"
    }, local.default_tags
  )
  force_destroy = true
}

locals {
  # Both buckets get the same hardening, so it is applied with for_each below.
  buckets = {
    input  = aws_s3_bucket.input_s3
    output = aws_s3_bucket.output_s3
  }
}

# Never allow public access.
resource "aws_s3_bucket_public_access_block" "this" {
  for_each = local.buckets

  bucket                  = each.value.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Encrypt objects at rest (SSE-S3).
resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  for_each = local.buckets

  bucket = each.value.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Refuse any request that is not sent over TLS.
data "aws_iam_policy_document" "deny_insecure_transport" {
  for_each = local.buckets

  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["s3:*"]
    resources = [
      each.value.arn,
      "${each.value.arn}/*",
    ]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "tls_only" {
  for_each = local.buckets

  bucket = each.value.id
  policy = data.aws_iam_policy_document.deny_insecure_transport[each.key].json

  # Applying a policy while the public access block is being changed can fail with a conflict.
  depends_on = [aws_s3_bucket_public_access_block.this]
}

# ---------------------------------------------------------------------------
# Container image registry + Lambda
# ---------------------------------------------------------------------------
module "ecr_repo" {
  source       = "../modules/ecr-repo"
  repo_name    = "${local.app_name}-ecr"
  default_tags = local.default_tags
}

module "lambda_function" {
  source                = "../modules/lambda"
  lambda_name           = "${local.app_name}-file-processor"
  role_name             = "${local.app_name}-file-processor-role"
  log_retention_in_days = 14
  image_uri             = "${module.ecr_repo.repository_url}:latest"
  architectures         = [var.lambda_architecture]
  timeout               = 60
  memory_size           = 512
  environment_variables = {
    OUTPUT_BUCKET = aws_s3_bucket.output_s3.id
    LOG_LEVEL     = "INFO"
  }

  default_tags = local.default_tags
}

# ---------------------------------------------------------------------------
# Least-privilege access for the Lambda role (on top of the CloudWatch Logs
# policy attached inside the lambda module):
#   * read objects from the input bucket only
#   * write objects to the output bucket only
# ---------------------------------------------------------------------------
data "aws_iam_policy_document" "lambda_s3_access" {
  statement {
    sid       = "ReadInputObjects"
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.input_s3.arn}/*"]
  }

  statement {
    sid       = "WriteOutputObjects"
    effect    = "Allow"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.output_s3.arn}/*"]
  }
}

resource "aws_iam_role_policy" "lambda_s3_access" {
  name   = "${local.app_name}-s3-access"
  role   = module.lambda_function.role_name
  policy = data.aws_iam_policy_document.lambda_s3_access.json
}

# ---------------------------------------------------------------------------
# S3 -> Lambda trigger
# ---------------------------------------------------------------------------
resource "aws_lambda_permission" "allow_bucket" {
  statement_id   = "AllowExecutionFromS3Bucket"
  action         = "lambda:InvokeFunction"
  function_name  = module.lambda_function.lambda_arn
  principal      = "s3.amazonaws.com"
  source_arn     = aws_s3_bucket.input_s3.arn # must be the bucket ARN, not its name
  source_account = data.aws_caller_identity.current.account_id
}

resource "aws_s3_bucket_notification" "s3_notification" {
  bucket = aws_s3_bucket.input_s3.id

  lambda_function {
    lambda_function_arn = module.lambda_function.lambda_arn
    events              = ["s3:ObjectCreated:*"]
    filter_suffix       = ".csv"
  }

  # S3 validates the invoke permission when the notification is created.
  depends_on = [aws_lambda_permission.allow_bucket]
}
