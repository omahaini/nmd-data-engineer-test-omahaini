# Outputs
output "lambda_arn" {
  value = aws_lambda_function.lambda_function.arn
}

output "role_name" {
  description = "Name of the Lambda execution role (used to attach extra policies)"
  value       = aws_iam_role.lambda_exec_role.name
}

output "lambda_name" {
  value = aws_lambda_function.lambda_function.function_name
}
