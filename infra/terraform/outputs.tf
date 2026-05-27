output "alb_dns_name" {
  description = "Public DNS of the Application Load Balancer."
  value       = aws_lb.main.dns_name
}

output "db_endpoint" {
  description = "RDS endpoint (reachable from inside the VPC)."
  value       = aws_db_instance.postgres.endpoint
}

output "cluster_arn" {
  description = "ECS cluster ARN."
  value       = aws_ecs_cluster.main.arn
}
