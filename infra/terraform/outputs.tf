output "rol_arn" {
  description = "Valor para la variable de repositorio PIPELINE_DOCTOR_ROLE_ARN."
  value       = aws_iam_role.github.arn
}

output "bucket" {
  description = "Valor para la variable de repositorio PIPELINE_DOCTOR_BUCKET."
  value       = aws_s3_bucket.huellas.bucket
}

output "region" {
  description = "Región donde se creó todo."
  value       = var.region
}
