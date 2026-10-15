variable "aws_profile" {
  description = "aws profile to use"
  type        = string
}

variable "region_name" {
  default = "us-west-2"
  type    = string
}

variable "candidate_name" {
  type = string
}

variable "env" {
  type    = string
  default = "dev"
}

variable "project" {
  type = string
}

variable "lambda_architecture" {
  description = "CPU architecture of the Lambda image. Must match the --platform used for docker build (arm64 <-> linux/arm64, x86_64 <-> linux/amd64)."
  type        = string
  default     = "arm64"

  validation {
    condition     = contains(["arm64", "x86_64"], var.lambda_architecture)
    error_message = "lambda_architecture must be either \"arm64\" or \"x86_64\"."
  }
}
