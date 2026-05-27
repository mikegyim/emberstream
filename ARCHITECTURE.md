# Architecture

This document walks through EmberStream's design, the reasoning behind
the major choices, and what would change at production scale.

## Component overview

```
┌──────────────────────────────────────────────────────────────────┐
│                       FastAPI Application                        │
│                                                                  │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│   │  REST router │    │  WS router   │    │ Query router │       │
│   │  /telemetry  │    │ /ws/telemetry│    │ /query (RAG) │       │
│   └──────┬───────┘    └──────┬───────┘    └──────┬───────┘       │
│          │                   │                   │               │
│   ┌──────▼───────┐    ┌──────▼───────┐    ┌──────▼───────┐       │
│   │   Ingest     │    │  Broadcaster │    │  RAG service │       │
│   │   service    │    │  (conn mgr)  │    │              │       │
│   └──────┬───────┘    └──────▲───────┘    └──────┬───────┘       │
│          │                   │                   │               │
└──────────┼───────────────────┼───────────────────┼───────────────┘
           │                   │                   │
   ┌───────▼───────────────────┴────┐    ┌─────────▼─────────┐
   │       Redis Streams            │    │  Postgres+pgvector │
   │       (event bus)              │    │                    │
   │                                │    │  - telemetry rows  │
   │   stream: telemetry-events     │    │  - vector(1536)    │
   │   consumer groups:             │    │  - HNSW index      │
   │   - broadcaster                │    │                    │
   │   - embedder                   │    └─────────▲──────────┘
   └────────────────────────────────┘              │
                                                   │
                                          ┌────────┴────────┐
                                          │ Embedding worker │
                                          │   Bedrock /      │
                                          │   OpenAI         │
                                          └──────────────────┘
```

## Data flow

### Write path

1. Client POSTs an event to `/telemetry` (or pushes via MQTT to a script
   that re-publishes to the REST endpoint).
2. The ingest service validates the event (Pydantic), assigns a UUID and
   server timestamp, and `XADD`s to the `telemetry-events` Redis stream.
3. Two consumer groups read from the stream:
   - **Broadcaster**: pushes the event JSON to every connected WebSocket
     client subscribed to `/ws/telemetry`.
   - **Embedder**: serializes the event to a short text representation,
     calls the embedding model (Bedrock Titan or OpenAI
     `text-embedding-3-small`), and inserts a row into the `telemetry`
     table containing both the raw fields and the 1536-dim vector.

### Query path (RAG)

1. Client POSTs `{"question": "..."}` to `/query`.
2. The RAG service embeds the question with the same model used for
   storage.
3. A `SELECT ... ORDER BY embedding <=> $1 LIMIT 8` against pgvector
   returns the 8 most semantically similar telemetry events.
4. The retrieved events are formatted into a context block and passed to
   the configured LLM (Bedrock Claude or OpenAI `gpt-4o-mini`) with a
   system prompt instructing it to answer using only the provided
   context.
5. The LLM response is returned along with the retrieved-context
   citations for verifiability.

## Why this shape

### Redis Streams as the event bus

Production-grade alternatives are Apache Kafka (MSK on AWS) or AWS
Kinesis. For a portfolio project, both are operationally heavy and
expensive (MSK starts around $0.10/hour per broker, three brokers
recommended). Redis Streams gives us:

- Consumer groups with at-least-once delivery semantics
- Message IDs we can replay from
- A familiar `XADD` / `XREADGROUP` surface
- ~50MB container, $0 to run locally

The event-bus interface (`services/stream.py`) is intentionally narrow so
a Kafka or Kinesis implementation drops in with a single-file change.

### pgvector for vectors

The telemetry data is small and structured. Keeping vectors alongside the
source rows in Postgres:

- Removes a second store from the stack
- Lets retrieval combine vector similarity with normal SQL filters
  (`WHERE sensor_id = $1 AND time > $2 ORDER BY embedding <=> $3`)
- Scales to a few million rows comfortably with HNSW indexing

Beyond that scale, dedicated vector stores (OpenSearch, Pinecone, Qdrant)
become worth the extra complexity.

### FastAPI

Async support, automatic OpenAPI generation, Pydantic v2 for validation,
and excellent WebSocket primitives. The same code surface a hiring
manager will see in any modern Python backend role.

### Bedrock first, OpenAI as fallback

The themed use case (DoD / public-sector telemetry) makes Bedrock the
realistic production target. Bedrock supports the Titan embedding model
and Anthropic Claude models with no data-egress-to-third-party concerns.
OpenAI is the dev convenience option.

## Security considerations

The service ships with the basics a senior engineer is expected to think
about:

- **Pydantic input validation** on every public endpoint
- **Parameterized SQL** via SQLAlchemy / asyncpg — no string concat
- **Secrets via environment** — `.env` is in `.gitignore`, `.env.example`
  documents the contract
- **No PII in logs** — structured logging redacts the `notes` field by
  default
- **Container scanning** (Trivy) in CI; high/critical CVEs fail the build
- **Secret scanning** (gitleaks) in CI
- **TLS termination at the ALB** in the AWS deploy
- **IAM least privilege** in the Terraform task role (only the Bedrock
  models actually used)

## What would change at production scale

| Concern | Portfolio choice | Production choice |
|---|---|---|
| Event bus | Redis Streams | Amazon MSK or Kinesis with multi-AZ |
| Vector store | pgvector single instance | Pinecone or OpenSearch Serverless |
| Embeddings | sync inline | async background worker pool |
| LLM calls | sync request/response | streaming over WebSocket, with caching |
| Auth | none / API key | OIDC + per-tenant scopes |
| DB | RDS db.t4g.micro single-AZ | Aurora Postgres multi-AZ |
| Deploy | single ECS Fargate task | Auto-scaling group, multi-AZ |
| Observability | Prometheus metrics | + OpenTelemetry traces, X-Ray |
| Network | public subnet only | private subnets, NAT, VPC endpoints |

The point is not that this project ships any of that — it doesn't, and
shouldn't. The point is that the trade-offs were considered and the
interfaces leave room for the upgrade path.
