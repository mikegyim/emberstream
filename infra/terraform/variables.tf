variable "region" {
  description = "AWS region for the deploy."
  type        = string
  default     = "us-east-1"
}

variable "image" {
  description = "Container image (e.g. ghcr.io/mikegyim/emberstream:abc1234)."
  type        = string
}

variable "image_tag" {
  description = "Tag-only convenience; concatenated with default GHCR repo if `image` is left blank."
  type        = string
  default     = "latest"
}

variable "db_password" {
  description = "Master password for the RDS instance. Pass via -var or TF_VAR_db_password."
  type        = string
  sensitive   = true
}

variable "redis_url" {
  description = "Redis Streams URL. For demo: spin up ElastiCache or run a single-node Redis on EC2."
  type        = string
  default     = "redis://redis.example:6379/0"
}

variable "enable_bedrock" {
  description = "Attach Bedrock InvokeModel permissions to the task role."
  type        = bool
  default     = false
}
