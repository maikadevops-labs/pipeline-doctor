variable "region" {
  description = "Región de AWS donde se crea el bucket (y desde donde se llama a Bedrock)."
  type        = string
  default     = "us-east-1"
}

variable "github_repositories" {
  description = "Repositorios de GitHub (formato dueño/repo) que pueden asumir el rol. Cada uno debe usar las Actions de Pipeline Doctor."
  type        = list(string)
  default     = ["maikadevops-labs/pipeline-doctor"]
}

variable "prefijo_bucket" {
  description = "Prefijo del nombre del bucket. Se le agrega el ID de la cuenta para que sea único."
  type        = string
  default     = "pipeline-doctor-huellas"
}

variable "dias_retencion" {
  description = "Días que se conservan las huellas antes de borrarse automáticamente."
  type        = number
  default     = 90
}

variable "bedrock_model_ids" {
  description = "IDs de modelos de Bedrock que el rol puede invocar. Admite comodines. Déjalo vacío para no dar permisos de Bedrock (modo sin IA)."
  type        = list(string)
  default     = ["amazon.nova-*"]
}

variable "crear_proveedor_oidc" {
  description = "Pon false si tu cuenta ya tiene un proveedor OIDC para token.actions.githubusercontent.com."
  type        = bool
  default     = true
}
