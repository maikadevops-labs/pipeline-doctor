# Infraestructura (Terraform)

Crea un bucket S3 privado para las huellas, el proveedor OIDC de GitHub y el rol `pipeline-doctor-github` con permisos mínimos.

```powershell
$env:AWS_PROFILE = "personal"      # tu perfil del AWS CLI
cd infra\terraform
copy terraform.tfvars.example terraform.tfvars   # edita github_repositories
terraform init
terraform validate
terraform apply
```

Al terminar, `terraform output` muestra `rol_arn`, `bucket` y `region`: son los valores de las variables del repositorio.

Si tu cuenta ya tiene el proveedor OIDC de GitHub, pon `crear_proveedor_oidc = false` en `terraform.tfvars`.

Para borrarlo todo: `terraform destroy`.

No subas a Git `terraform.tfvars` ni `*.tfstate` (ya están en `.gitignore`).
