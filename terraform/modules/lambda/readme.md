This sets up an AWS Lambda function with the following resources:
- IAM Role for execution
- IAM Role Policy attachment for CloudWatch logging
- CloudWatch Log Group for function logs
- Lambda function using a container image

How to use:
```
module "lambda_deployment" {
  source = "./path-to-this-module"

  role_name             = "my-lambda-exec-role"
  lambda_name           = "my-lambda-function"
  image_uri             = "123456789012.dkr.ecr.us-east-1.amazonaws.com/my-lambda-image:latest"
  log_retention_in_days = 7
  timeout               = 15
  memory_size           = 128
  environment_variables = {
    KEY = "value"
  }
  default_tags = {
    Environment = "Production"
    Team        = "Backend"
  }
}
```

Inputs:
Name| Description| Type| Required
|--|--|--|--|
role_name| Name of the IAM Role for the Lambda function.| string| Yes
lambda_name| Name of the Lambda function.| string| Yes
image_uri| URI of the container image for the Lambda function.| string| Yes
log_retention_in_days| Number of days to retain logs in CloudWatch.| number| Yes
timeout| Timeout for the Lambda function in seconds.| number| Yes
memory_size| Memory size for the Lambda function in MB.| number| Yes
environment_variables| Environment variables for the Lambda function.| map(string)| No
default_tags| Tags for all created resources.| map| No
architectures| Lambda instruction set, e.g. ["arm64"]. Must match the image platform (default ["x86_64"]).| list(string)| No

Outputs: `lambda_arn`, `lambda_name`, `role_name`.