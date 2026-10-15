provider "aws" {
  region  = var.region_name
  profile = var.aws_profile
}
data "aws_caller_identity" "current" {}

terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }

  # The remote state backend normally goes here - see the note below.
}

# ---------------------------------------------------------------------------
# REMOTE STATE BACKEND - TEMPORARILY DISABLED
# The state bucket "nmd-training-tf-states-706146613458" does not exist (S3
# returns NoSuchBucket), so `terraform init` fails with it enabled. State is
# kept locally until the bucket is provided. To restore it, move this block
# inside the terraform { } block above (and fix the bucket name if needed),
# then run:
#   terraform init -migrate-state -backend-config="key=nmd-assignment-<candidate-name>.tfstate"
# ---------------------------------------------------------------------------
# terraform {
#   backend "s3" {
#     bucket         = "nmd-training-tf-states-706146613458"
#     ## update the key value to a unique value for your assignment
#     # key            = "assignment/update-the-name-here-nmd-assignment.tfstate"
#     region         = "us-west-2"
#     dynamodb_table = "nmd-training-tf-state-lock-table"
#     encrypt        = true                   # Encrypts the state file at rest
#   }
# }
