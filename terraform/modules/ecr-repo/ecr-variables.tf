
# Variables
variable "repo_name" {}

variable "default_tags" {
  type        = map(string)
  description = "Default tags to apply to all resources"
}