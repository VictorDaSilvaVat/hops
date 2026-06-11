# HOPS — Bitcoin Forensics Platform

## Entrypoints

- **`dashboardpro.py`** — Streamlit UI entrypoint. Run with `streamlit run dashboardpro.py`.
- **`btc_forensics_pro.py`** — `BTCForensicsPro` is the main orchestrator (tracing, analysis, AI reports).
- **`forensic_report_v2.py`** — `EnhancedForensicReporter` generates PDF/HTML reports with charts.

## Config

- `config.py` uses plain dataclasses + `os.getenv()` — no Pydantic, no pydantic-settings.
- `dashboardpro.py` reads env vars again directly at module top — both paths must be kept in sync.
- All env vars and defaults documented in `config.py` and `docker-compose.yml`.
- No `.env.example` exists (README says `cp .env.example .env` but file is missing).

## Architecture

Hexagonal (ports/adapters) layout but implemented as a single flat package:

```
domain/          — models (Address, EntityType), ports, services
infrastructure/  — adapters: Neo4j, Blockstream, WalletExplorer, OpenRouter, reporting
```

`BTCForensicsPro` accepts DI for all adapters/services in its constructor. When not provided, defaults are created internally.

## Dependencies

Plain `requirements.txt` — no pyproject.toml, no pip-compile, no lockfile.

```bash
pip install -r requirements.txt
```

No test framework, no linter, no type checker, no formatter configured.

## Deployment (Coolify / Docker Compose)

- Two services: `neo4j` (neo4j:5-community) + `app` (custom Dockerfile).
- `neo4j` uses `NEO4J_AUTH` format and health check with `cypher-shell`.
- **Neo4j 5.x quirk**: strict config validation enabled by default. All env vars starting with `NEO4J_` are interpreted as config; unrecognized ones crash the container. The fix is `NEO4J_server_config_strict__validation_enabled=false` (already added).

## Important Gotchas

- `dashboardpro.py` reads `NEO4J_PASSWORD` directly — NOT through `Config`. Adding a new env var to `config.py` must be mirrored there.
- `dashboardpro.py` default `AI_PROVIDER=ollama`, but `docker-compose.yml` defaults to `openrouter`.
- Reports are stored in `reports/<address>/<timestamp>/`. The `hops_reports` Docker volume persists this.
- `SANCTIONS_INTERNAL_KEY` is read via `os.environ.get` directly in `check_sanctions` — not through `Config`. It must be set as an env var (Coolify / docker-compose).
- `get_transaction_history` in `neo4j_adapter.py` was fixed to use an undirected match `(address)-[:SENT]-(connected)` so both incoming and outgoing transactions are included in balance calculations.

## Report Generation

`EnhancedForensicReporter` produces per-analysis folders under `reports/` containing: PDF, HTML, PNG charts (timeline, heatmap, graph), CSV transactions, JSON metadata.
