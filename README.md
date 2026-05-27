# EmberStream

[![CI](https://github.com/mikegyim/emberstream/actions/workflows/ci.yml/badge.svg)](https://github.com/mikegyim/emberstream/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A real-time telemetry ingestion platform with a natural-language query layer.
Telemetry events stream in over REST or MQTT, fan out to live WebSocket subscribers,
get persisted to Postgres with vector embeddings, and become queryable in natural
language via a small RAG (Retrieval-Augmented Generation) layer.

Built as a portfolio demonstration of senior-level Python backend, real-time
streaming, cloud-native deployment, DevSecOps, and GenAI integration patterns.

---

## What this project demonstrates

| Capability | Where in the code |
|---|---|
| **FastAPI backend** with async handlers | [`src/emberstream/main.py`](src/emberstream/main.py) |
| **WebSocket** live data fan-out | [`routers/ws.py`](src/emberstream/routers/ws.py), [`services/broadcast.py`](src/emberstream/services/broadcast.py) |
| **REST API** with OpenAPI auto-docs | [`routers/telemetry.py`](src/emberstream/routers/telemetry.py) |
| **Real-time streaming** via Redis Streams (Kafka-compatible patterns) | [`services/stream.py`](src/emberstream/services/stream.py) |
| **Vector store + RAG** with pgvector + LLM | [`services/rag.py`](src/emberstream/services/rag.py), [`services/embeddings.py`](src/emberstream/services/embeddings.py) |
| **Pytest** unit + integration tests | [`tests/`](tests/) |
| **Multi-stage Docker** build | [`Dockerfile`](Dockerfile) |
| **docker-compose** local dev (app + Postgres+pgvector + Redis) | [`docker-compose.yml`](docker-compose.yml) |
| **Terraform IaC** for AWS deployment | [`infra/terraform/`](infra/terraform/) |
| **GitHub Actions CI/CD** with lint, test, build, container scan | [`.github/workflows/ci.yml`](.github/workflows/ci.yml) |
| **Prometheus metrics** endpoint | [`utils/metrics.py`](src/emberstream/utils/metrics.py) |
| **Structured logging** + correlation IDs | [`utils/logging.py`](src/emberstream/utils/logging.py) |
| **Security scanning** (Trivy, gitleaks, ruff) in CI | [`.github/workflows/ci.yml`](.github/workflows/ci.yml) |

---

## Architecture

```mermaid
flowchart LR
    subgraph Ingest
      MQTT[MQTT publisher<br/>scripts/mqtt_publisher.py]
      REST[REST POST /telemetry]
    end

    subgraph App[FastAPI Service]
      API[REST + WebSocket routers]
      ING[Ingest service]
      BCAST[WebSocket broadcaster]
      EMB[Embedding service]
      RAG[RAG query service]
    end

    subgraph Storage
      REDIS[(Redis Streams<br/>event bus)]
      PG[(Postgres + pgvector<br/>telemetry + embeddings)]
    end

    LLM[Amazon Bedrock<br/>or OpenAI]
    UI[Dashboard / curl /<br/>WebSocket clients]

    MQTT --> ING
    REST --> ING
    ING --> REDIS
    REDIS --> BCAST
    REDIS --> EMB
    EMB --> PG
    BCAST --> UI
    UI -->|/query "natural language"| RAG
    RAG --> PG
    RAG --> LLM
    LLM --> RAG
    RAG --> UI
```

A telemetry event enters via REST (`POST /telemetry`) or MQTT. The ingest
service writes it to Redis Streams as the canonical event bus. Two consumers
read from the stream: the **broadcaster** fans the event out to any WebSocket
clients subscribed to `/ws/telemetry`, and the **embedding worker** generates
a vector embedding of the event payload and persists both the raw record and
the embedding to Postgres (using `pgvector`).

When a user POSTs a natural-language question to `/query`, the **RAG service**
embeds the question, runs a vector similarity search against the telemetry
embeddings in Postgres, builds a prompt with the top-k retrieved events as
context, and calls Bedrock (or OpenAI) to generate a grounded answer.

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for a deeper walkthrough including
trade-offs, scaling notes, and security considerations.

---

## Quick start (local)

You need Docker and Docker Compose. Nothing else.

```bash
git clone https://github.com/mikegyim/emberstream.git
cd emberstream
cp .env.example .env          # fill in BEDROCK or OPENAI_API_KEY (optional)
docker compose up --build
```

The app is up at <http://localhost:8000>. OpenAPI docs live at
<http://localhost:8000/docs>. Prometheus metrics at <http://localhost:8000/metrics>.

### Send a telemetry event

```bash
curl -X POST http://localhost:8000/telemetry \
  -H "Content-Type: application/json" \
  -d '{"sensor_id":"sensor-01","kind":"temperature","value":42.7,"location":"grid-A-7","notes":"slight uptick after sunrise"}'
```

### Subscribe to the live feed

```bash
# Using websocat (https://github.com/vi/websocat)
websocat ws://localhost:8000/ws/telemetry
```

You'll see events stream in real time as they are POSTed.

### Generate sample data

```bash
docker compose exec app python -m scripts.seed_telemetry --count 500
```

### Ask a natural-language question

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Which sensors showed unusual temperature spikes today?"}'
```

(Requires `BEDROCK_*` or `OPENAI_API_KEY` set; otherwise the route returns the
retrieved context without LLM synthesis so you can verify retrieval works.)

---

## Tech stack

- **Python 3.11**, **FastAPI**, **uvicorn**, **Pydantic v2**
- **PostgreSQL 16** with **pgvector** for hybrid relational + vector storage
- **Redis Streams** as the event bus (Kafka-compatible producer/consumer
  patterns; swap to MSK / Kinesis in production)
- **Amazon Bedrock** (Anthropic Claude / Titan Embeddings) with OpenAI as
  fallback
- **Docker** + **docker-compose** for local dev
- **Terraform** for AWS deploy (ECS Fargate + RDS + ALB)
- **GitHub Actions** for CI/CD
- **Trivy**, **gitleaks**, **ruff**, **mypy**, **pytest** for code quality
  and security gates
- **Prometheus** instrumentation via `prometheus-fastapi-instrumentator`

---

## Design decisions and trade-offs

A few choices a reviewer might ask about:

**Why Redis Streams over Kafka or Kinesis?** For a portfolio project the
operational footprint of MSK or self-hosted Kafka is too heavy. Redis Streams
exposes a similar API (consumer groups, acks, message IDs) and runs in a
single 50MB container. The ingest and consumer code is written against an
abstract `EventBus` interface so swapping to Kafka or Kinesis is a one-file
change.

**Why pgvector over Pinecone / OpenSearch / Chroma?** Storing telemetry data
and its vector embedding in the same database simplifies the data model and
removes a network hop on the read path. pgvector handles up to a few million
vectors well; beyond that, OpenSearch Serverless or Pinecone become more
appropriate. The retrieval layer is encapsulated in `services/rag.py` so the
vector store is swappable.

**Why ECS Fargate over EKS for the deploy target?** EKS adds a $73/month
control-plane fee and requires a NAT Gateway (~$33/month) for private-subnet
clusters. Fargate has no control-plane cost and the same image runs unchanged.
EKS Helm chart is included for the case where a hiring manager wants to see
Kubernetes-native deployment.

**Why include both Bedrock and OpenAI?** Bedrock is the realistic target for
the GovCloud / Public Sector use cases this project is themed around, but
OpenAI is cheaper for local development. The `LLMProvider` interface lets you
swap between them with one env var.

---

## Running tests

```bash
docker compose exec app pytest -v
# or locally with deps installed:
pip install -e ".[dev]"
pytest -v
```

The suite includes:

- Unit tests for the broadcaster, ingest, embedding, and RAG services
- An integration test that POSTs an event, asserts it appears on the WebSocket
  feed, and asserts a similarity search retrieves it
- A contract test against the OpenAPI schema

---

## Deploying to AWS

Costs ~$15–25 for a 24-hour demo if you tear it down after.

```bash
cd infra/terraform
terraform init
terraform apply -var="image_tag=$(git rev-parse --short HEAD)"
# ... demo, record video, take screenshots ...
terraform destroy
```

The module provisions:

- A small VPC (single public subnet — no NAT Gateway)
- An ECS Fargate service running the app image from GitHub Container Registry
- An RDS `db.t4g.micro` Postgres instance with `pgvector` enabled
- An Application Load Balancer fronting the Fargate service
- CloudWatch Logs for app stdout

See [`infra/terraform/README.md`](infra/terraform/README.md) for details and
cost notes.

---

## CI/CD pipeline

`.github/workflows/ci.yml` runs on every push:

1. **Lint**: ruff + mypy
2. **Test**: pytest with Postgres + Redis service containers
3. **Build**: multi-stage Docker image, pushed to GHCR on `main`
4. **Scan**: Trivy filesystem + container scan, gitleaks secrets scan
5. **Quality gate**: any high/critical CVE or secret leak fails the build

---

## Roadmap / "if I had more time"

- Helm chart with `values.yaml` for multi-environment overrides
- OpenTelemetry traces alongside Prometheus metrics
- Per-tenant API keys and rate limiting
- Streaming response from RAG (token-by-token over WebSocket)
- Migrate event bus to MSK or Kinesis for the production deploy target

---

## License

[MIT](LICENSE)

---

Built by [Michael Opoku-Gyimah](https://www.linkedin.com/in/michael-o-g-6b82731b3/) as a portfolio demonstration.
