
resource "aws_ecr_repository" "lambda_repo" {
  name = var.repo_name

  tags = var.default_tags

  force_delete = true
}

