AWS ECR Repository Module

This creates an ECR repository for storing and managing container images.

How to Use
```
module "lambda_repo" {
  source = "./path-to-this-module"

  repo_name     = "my-lambda-repo"
  default_tags  = {
    Environment = "Production"
    Team        = "DevOps"
  }
}
```

Inputs

| Name | Description| Required|
|--|--|--|
repo_name|	Name of the ECR repository.	|Yes
default_tags|Tags for the repository (optional).|No
