# EmberStream Terraform

Minimal-footprint AWS deploy of the EmberStream app.

## What you get

- VPC with two public subnets across two AZs (no NAT Gateway — see notes)
- ECS Fargate service (1 task, 512 CPU / 1024 MB)
- Application Load Balancer on port 80
- RDS `db.t4g.micro` Postgres with `pgvector` enabled
- CloudWatch Logs for app stdout

## Cost notes (us-east-1, on-demand)

| Resource | ~Hourly | ~Monthly |
|---|---|---|
| ALB | $0.0225 + LCU | ~$16 |
| Fargate task (0.5 vCPU / 1 GB) | $0.025 | ~$18 |
| RDS db.t4g.micro | $0.018 | ~$13 |
| CloudWatch Logs | usage | <$1 |

A 24-hour demo runs about **$1–2**. The full month if you forget to destroy is
around **$50**. There is no NAT Gateway (the big classic billing trap is
avoided because Fargate runs in public subnets with `assign_public_ip = true`).

## How to deploy

```bash
# Build and push the image (or rely on GitHub Actions to do it)
docker build -t ghcr.io/mikegyim/emberstream:demo .
docker push ghcr.io/mikegyim/emberstream:demo

cd infra/terraform
terraform init
TF_VAR_db_password='choose-a-strong-one' terraform apply \
  -var "image=ghcr.io/mikegyim/emberstream:demo"

# ... grab the alb_dns_name from outputs, demo, screenshot, record ...

terraform destroy
```

## Production notes

For an actual production deploy you would change:

- Move ECS tasks to private subnets behind a NAT Gateway or VPC endpoints
- Enable RDS multi-AZ, automated backups, encryption
- Terminate TLS at the ALB with ACM certs
- Add WAF rules in front of the ALB
- Use Secrets Manager for the DB password instead of `-var`
- Run Redis on ElastiCache (multi-AZ) instead of self-hosted
- Replace Redis Streams with MSK or Kinesis for durability at scale

These are all `terraform apply` away once the workload justifies the cost.
