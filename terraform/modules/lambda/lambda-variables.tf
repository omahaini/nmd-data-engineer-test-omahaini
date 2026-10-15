# Variables
variable "lambda_name" {}
variable "role_name" {}
variable "log_retention_in_days" { default = 14 }
variable "image_uri" {}
variable "timeout" { default = 10 }
variable "memory_size" { default = 128 }

variable "environment_variables" {
  type    = map(string)
  default = {}
}

variable "default_tags" {
  type        = map(string)
  description = "Default tags to apply to all resources"
}

variable "architectures" {
  type        = list(string)
  default     = ["x86_64"]
  description = "Instruction set of the function. Must match the platform the container image was built for."
}
