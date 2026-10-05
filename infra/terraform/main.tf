data "aws_caller_identity" "actual" {}
data "aws_partition" "actual" {}

locals {
  nombre_bucket = "${var.prefijo_bucket}-${data.aws_caller_identity.actual.account_id}"

  arn_proveedor_oidc = (
    var.crear_proveedor_oidc
    ? aws_iam_openid_connect_provider.github[0].arn
    : "arn:${data.aws_partition.actual.partition}:iam::${data.aws_caller_identity.actual.account_id}:oidc-provider/token.actions.githubusercontent.com"
  )

  recursos_bedrock = flatten([
    for id in var.bedrock_model_ids : [
      "arn:${data.aws_partition.actual.partition}:bedrock:*::foundation-model/${id}",
      "arn:${data.aws_partition.actual.partition}:bedrock:*:${data.aws_caller_identity.actual.account_id}:inference-profile/*.${id}",
    ]
  ])
}

# --- Bucket privado donde viven las huellas ------------------------------------------------

resource "aws_s3_bucket" "huellas" {
  bucket        = local.nombre_bucket
  force_destroy = true # las huellas son desechables: así `terraform destroy` limpia todo
}

resource "aws_s3_bucket_public_access_block" "huellas" {
  bucket                  = aws_s3_bucket.huellas.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "huellas" {
  bucket = aws_s3_bucket.huellas.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "huellas" {
  bucket = aws_s3_bucket.huellas.id

  rule {
    id     = "expirar-huellas"
    status = "Enabled"

    filter {
      prefix = "huellas/"
    }

    expiration {
      days = var.dias_retencion
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}

data "aws_iam_policy_document" "solo_tls" {
  statement {
    sid     = "DenegarSinTLS"
    effect  = "Deny"
    actions = ["s3:*"]

    resources = [
      aws_s3_bucket.huellas.arn,
      "${aws_s3_bucket.huellas.arn}/*",
    ]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "huellas" {
  bucket     = aws_s3_bucket.huellas.id
  policy     = data.aws_iam_policy_document.solo_tls.json
  depends_on = [aws_s3_bucket_public_access_block.huellas]
}

# --- GitHub Actions entra a AWS por OIDC, sin access keys -----------------------------------

resource "aws_iam_openid_connect_provider" "github" {
  count = var.crear_proveedor_oidc ? 1 : 0

  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]

  # AWS ya no valida este valor para GitHub, pero versiones antiguas del proveedor lo exigen.
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

data "aws_iam_policy_document" "confianza_github" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [local.arn_proveedor_oidc]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # Solo los repositorios de la lista pueden asumir este rol.
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      # GitHub puede incluir los IDs numéricos en el claim: repo:dueño@ID/repo@ID:ref:...
      # Se aceptan ambos formatos, siempre del mismo dueño y repo.
      values = flatten([
        for repo in var.github_repositories : [
          "repo:${repo}:*",
          "repo:${split("/", repo)[0]}@*/${split("/", repo)[1]}@*:*",
        ]
      ])
    }
  }
}

resource "aws_iam_role" "github" {
  name                 = "pipeline-doctor-github"
  assume_role_policy   = data.aws_iam_policy_document.confianza_github.json
  max_session_duration = 3600
}

# --- Permisos mínimos: leer/escribir huellas y (opcional) invocar modelos de Bedrock ---------

data "aws_iam_policy_document" "permisos" {
  statement {
    sid       = "HuellasObjetos"
    effect    = "Allow"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${aws_s3_bucket.huellas.arn}/huellas/*"]
  }

  statement {
    sid       = "HuellasListar"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.huellas.arn]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["huellas/*"]
    }
  }

  dynamic "statement" {
    for_each = length(local.recursos_bedrock) > 0 ? [1] : []

    content {
      sid       = "BedrockInvocar"
      effect    = "Allow"
      actions   = ["bedrock:InvokeModel"] # la API Converse usa este permiso
      resources = local.recursos_bedrock
    }
  }
}

resource "aws_iam_role_policy" "permisos" {
  name   = "huellas-y-bedrock"
  role   = aws_iam_role.github.id
  policy = data.aws_iam_policy_document.permisos.json
}
