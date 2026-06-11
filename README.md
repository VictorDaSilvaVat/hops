# HOPS Cloud — Bitcoin Forensics Platform

**HOPS** (Hop Oracle for Pattern Surveillance) is a Bitcoin transaction forensics platform that traces, analyzes, and visualizes blockchain transactions. It generates AI-powered forensic reports with interactive graphs, timeline/heatmap charts, sanctions checking, and downloadable PDF reports.

---

## Features

- 🔍 **Transaction tracing** — Follow Bitcoin transactions forward (fan-out) and backward (fan-in) through multiple hops
- 🧠 **AI-powered analysis** — Generate forensic reports using **OpenRouter** (cloud) or **Ollama** (local)
- 🚦 **Sanctions checking** — Query sanctions lists for any Bitcoin address
- 📊 **Interactive visualizations** — PyVis transaction graphs, Sankey flows, timeline, and heatmap
- 📄 **PDF reports** — Complete forensic reports with embedded charts, graphs, and transaction tables
- 🗂️ **Per-analysis folders** — All data exported as JSON, CSV, and HTML for future editing
- 🐳 **Coolify-ready** — One-click deploy with Docker Compose (app + Neo4j)

---

## Quick Start

### Local development

```bash
# 1. Clone and enter the directory
git clone <your-repo> hops_cloud
cd hops_cloud

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
.venv\Scripts\activate      # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start Neo4j (Docker)
docker run -d --name hops-neo4j \
  -e NEO4J_AUTH=neo4j/neo4jneo4j \
  -p 7687:7687 -p 7474:7474 \
  neo4j:5-community

# 5. Run the dashboard
streamlit run dashboardpro.py
```

Open http://localhost:8501 in your browser.

### AI Provider Setup

#### Option A: OpenRouter (recommended — no GPU needed)

```bash
# Set your API key (get one at https://openrouter.ai/keys)
export OPENROUTER_API_KEY=sk-or-v1-your-key-here
export AI_PROVIDER=openrouter
export AI_MODEL=google/gemini-2.0-flash-001

streamlit run dashboardpro.py
```

#### Option B: Ollama (local — requires GPU)

```bash
# Install and run Ollama
ollama pull llama3
ollama serve

export AI_PROVIDER=ollama
streamlit run dashboardpro.py
```

---

## Deployment with Coolify

### One-click deploy using Docker Compose

1. Push this repo to GitHub/GitLab
2. In Coolify, create a **Docker Compose** service
3. Point it to your repo
4. Add these **Environment Variables** in Coolify:

| Variable | Default | Description |
|----------|---------|-------------|
| `NEO4J_USER` | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | `neo4jneo4j` | Neo4j password |
| `AI_PROVIDER` | `openrouter` | `openrouter` or `ollama` |
| `AI_MODEL` | `google/gemini-2.0-flash-001` | Model name for the AI provider |
| `OPENROUTER_API_KEY` | *(required)* | Your OpenRouter API key |
| `MAX_HOPS` | `2` | Transaction trace depth |

5. Deploy — Coolify will build the image and start both containers

### Manual Docker deployment

```bash
# Create .env from example
cp .env.example .env
# Edit .env with your settings

# Start everything
docker compose up -d
```

The app will be available at `http://<your-host>:8501`.

---

## Accessing the Dashboard

Once deployed, open the dashboard in your browser:

| Environment | URL |
|-------------|-----|
| **Local** | `http://localhost:8501` |
| **Coolify** | `https://<proyecto>.<dominio-coolify>` (asignado automáticamente) |
| **VPS directo** | `http://<IP_DEL_VPS>:8501` |
| **Con dominio propio** | `https://tudominio.com` (configurando DNS + proxy en Coolify) |

**Neo4j Browser** (para explorar el grafo directamente):
`http://<IP>:7474` — usuario/contraseña según `NEO4J_USER` / `NEO4J_PASSWORD`.

**Firewall**: asegúrate de que los puertos `8501` (app) y `7687` (Neo4j Bolt) estén abiertos. En Coolify los puertos se exponen automáticamente según tu `docker-compose.yml`.

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `NEO4J_URI` | No | `bolt://localhost:7687` | Neo4j connection URI |
| `NEO4J_USER` | No | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | No | `neo4jneo4j` | Neo4j password |
| `AI_PROVIDER` | No | `ollama` | AI provider: `ollama` or `openrouter` |
| `AI_MODEL` | No | `llama3` or `google/gemini-2.0-flash-001` | Model name (depends on provider) |
| `OPENROUTER_API_KEY` | For OpenRouter | — | API key from https://openrouter.ai/keys |
| `MAX_HOPS` | No | `2` | Maximum trace depth |

---

## Dashboard Features — What Each Tab Does

Once you enter a Bitcoin address and click **Procesar**, the dashboard shows 8 tabs with the following forensic data:

### Filtros (sidebar)

| Filtro | Efecto |
|--------|--------|
| **Monto mínimo** | Oculta transacciones por debajo de este valor (anti-dust, default 0.00001 BTC) |
| **Solo hop 1** | Muestra solo relaciones directas con la dirección analizada (salta hops 2+) |
| **Ocultar change outputs** | Filtra las transacciones de "cambio" que el emisor envía de vuelta a su propia wallet |
| **Solo FAN-IN** | Muestra solo transacciones donde la dirección **recibe** fondos (entrantes) |
| **Solo FAN-OUT** | Muestra solo transacciones donde la dirección **envía** fondos (salientes) |
| **Filtrar por entidad** | Filtra por tipo de wallet (exchange, mixer, bridge, sanctioned, etc.) |

### Pestañas de visualización

| Pestaña | Qué representa |
|---------|----------------|
| **Grafo** | Mapa interactivo de conexiones entre direcciones. Cada nodo es una dirección BTC, cada flecha es una transacción. El color del nodo indica el tipo de entidad (exchange=azul, mixer=rojo, sanctioned=negro). |
| **Sankey** | Diagrama de flujo que agrupa y suma todas las transacciones entre pares de direcciones. Muestra los 200 flujos más grandes ordenados por volumen. Útil para ver hacia dónde va la mayor parte del dinero. |
| **Heatmap** | Distribución de montos por hora del día (UTC). Ayuda a identificar patrones temporales — por ejemplo, actividad consistente en horario laboral europeo sugiere una entidad regulada, mientras que actividad a todas horas puede indicar un mixer o bot. |
| **Timeline** | Evolución temporal de los montos transaccionados. Cada punto es una transacción. Permite identificar picos de actividad, periodos de inactividad, y patrones de comportamiento en el tiempo. |
| **Tabla** | Listado detallado de cada transacción individual con: dirección origen, destino, monto, TXID, hop, timestamp, tipo de entidad, y labels de WalletExplorer. |
| **Riesgo** | Panel resumen con métricas clave: total entrante, total saliente, vecinos únicos. |
| **Reporte IA** | Genera un informe forense narrativo usando IA (OpenRouter/Ollama). El botón simple usa solo el resumen de transacciones. El botón completo genera un reporte **PDF + HTML + gráficos + datos** en una carpeta por análisis. |
| **Grafo Detallado** | Visualización interactiva 3D del grafo de transacciones usando PyVis. Similar al Grafo simple pero con más detalles (tooltips con montos, TXIDs) y física de nodos ajustable. |

### Conceptos clave

- **Hop**: cada salto en la cadena de transacciones. Hop 1 son relaciones directas con la dirección analizada. Hop 2 son relaciones de segundo grado (los contactos de tus contactos).
- **FAN-IN**: transacciones entrantes — direcciones que enviaron fondos a la dirección analizada.
- **FAN-OUT**: transacciones salientes — direcciones que recibieron fondos desde la dirección analizada.
- **Change output**: cuando una wallet envía fondos, el sobrante vuelve a una dirección controlada por el mismo dueño. Detectar change outputs ayuda a identificar direcciones pertenecientes a la misma entidad.
- **Entity type**: clasificación de la dirección según WalletExplorer (exchange, mixer, gambling, etc.) o por heurísticas internas (bridge, sanctioned, individual).

---

```
┌─────────────────────────────────────────────────────┐
│                   Streamlit Dashboard                │
│  (dashboardpro.py)                                   │
├─────────────────────────────────────────────────────┤
│                  BTCForensicsPro                     │
│  (btc_forensics_pro.py)                              │
│                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │  Blockchain   │  │  Wallet API  │  │  Sanctions │ │
│  │  (Blockstream)│  │ (WalletExp.) │  │    API     │ │
│  └──────────────┘  └──────────────┘  └────────────┘ │
│                                                      │
│  ┌──────────────────┐   ┌──────────────────┐        │
│  │   Ollama /        │   │   Neo4j GraphDB  │        │
│  │   OpenRouter AI   │   │                  │        │
│  └──────────────────┘   └──────────────────┘        │
├─────────────────────────────────────────────────────┤
│              EnhancedForensicReporter                │
│  (forensic_report_v2.py)                             │
│  • PDF generation (fpdf2)                            │
│  • Chart generation (matplotlib)                     │
│  • HTML report + data exports                        │
└─────────────────────────────────────────────────────┘
```

### Key modules

| File | Purpose |
|------|---------|
| `btc_forensics_pro.py` | Main orchestrator — tracing, analysis, report generation |
| `dashboardpro.py` | Streamlit UI with filters, tabs, and download buttons |
| `forensic_report_v2.py` | PDF/HTML report builder with chart generation |
| `infrastructure/external/openrouter_client.py` | OpenRouter AI client (cloud LLM) |
| `infrastructure/persistence/neo4j_adapter.py` | Neo4j graph database adapter |
| `infrastructure/adapters/blockstream_adapter.py` | Blockstream blockchain API adapter |
| `infrastructure/adapters/wallet_explorer_adapter.py` | WalletExplorer entity recognition |
| `domain/` | Domain models, ports, and services (hexagonal architecture) |

---

## Report Structure

Each analysis run creates a timestamped folder under `reports/<address>/<timestamp>/`:

```
reports/
└── bc1q.../
    └── 20260525T120000Z/
        ├── report.pdf                 # Full forensic report (PDF)
        ├── report.html                # Full forensic report (HTML)
        ├── transaction_graph.html     # Interactive PyVis graph
        ├── timeline_chart.png         # Timeline visualization
        ├── heatmap_chart.png          # Hourly distribution chart
        ├── graph_chart.png            # Static network graph
        ├── transactions.csv           # Transaction table
        ├── analysis_metadata.json     # All structured data
        ├── timeline_data.json         # Raw timeline data
        ├── heatmap_data.json          # Raw heatmap data
        └── sankey_data.json           # Sankey flow data
```

---

## Available OpenRouter Models

Defined in `infrastructure/external/openrouter_client.py`:

- `google/gemini-2.0-flash-001` (default)
- `google/gemini-2.0-flash-lite-001`
- `openai/gpt-4o-mini`
- `openai/gpt-4o`
- `anthropic/claude-3.5-haiku`
- `anthropic/claude-3.5-sonnet`
- `meta-llama/llama-3.1-8b-instruct`
- `meta-llama/llama-3.1-70b-instruct`
- `mistralai/mistral-7b-instruct`
- `deepseek/deepseek-chat`
- `qwen/qwen-2.5-7b-instruct`

---

## License

MIT
