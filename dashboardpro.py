import streamlit as st
import pandas as pd
import networkx as nx
import altair as alt
from neo4j import GraphDatabase
from btc_forensics_pro import BTCForensicsPro
from forensic_report_v2 import EnhancedForensicReporter
import time
import json
import base64
import html
import os
import zipfile
import io
import tempfile
import uuid
from datetime import datetime, timezone
from pyvis.network import Network
import streamlit.components.v1 as components
import base58
import hashlib
import re

# -------------------------
# Address validation for all chains
# -------------------------
def is_valid_trx_address(addr: str) -> bool:
    if len(addr) != 34 or not addr.startswith("T"):
        return False
    try:
        raw = base58.b58decode(addr)
        if len(raw) != 25:
            return False
        data, checksum = raw[:-4], raw[-4:]
        h = hashlib.sha256(hashlib.sha256(data).digest()).digest()[:4]
        return h == checksum and data[0] == 0x41
    except Exception:
        return False

BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"

BASE58_CHARS = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")

def _btc_validation_error(addr: str) -> str:
    if not addr:
        return "Dirección vacía."
    if addr.startswith(("bc1", "BC1")):
        if len(addr) < 42:
            return f"Muy corta ({len(addr)} chars, mínimo 42 para bech32)."
        if len(addr) > 62:
            return f"Muy larga ({len(addr)} chars, máximo 62)."
        bad = [c for c in addr[3:].lower() if c not in BECH32_CHARSET]
        if bad:
            return f"Caracteres inválidos en bech32: {set(bad)}."
        return "Formato bech32 inválido."
    if addr.startswith(("1", "3")):
        if len(addr) < 26:
            return f"Muy corta ({len(addr)} chars, mínimo 26)."
        if len(addr) > 35:
            return f"Muy larga ({len(addr)} chars, máximo 35)."
        bad = [c for c in addr if c not in BASE58_CHARS]
        if bad:
            return f"Caracteres inválidos (0,O,I,l no son válidos en base58): {set(bad)}."
        return "Error de checksum — Blockstream la rechazó como inválida."
    return "Debe comenzar con 1, 3 o bc1 (mainnet)."

def is_valid_btc_address(addr: str) -> bool:
    """Basic format check (prefix + length + base58 charset). API validates checksum."""
    if not addr:
        return False
    if addr.startswith("bc1") or addr.startswith("BC1"):
        return 42 <= len(addr) <= 62 and all(c in BECH32_CHARSET for c in addr[3:].lower())
    if addr.startswith("1") or addr.startswith("3"):
        return 26 <= len(addr) <= 35 and all(c in BASE58_CHARS for c in addr)
    return False

def is_valid_eth_address(addr: str) -> bool:
    return bool(re.fullmatch(r"0x[a-fA-F0-9]{40}", addr))

def is_valid_bch_address(addr: str) -> bool:
    if not addr:
        return False
    if addr.startswith("bitcoincash:"):
        addr = addr[12:]
    if addr.startswith(("q", "Q", "p", "P")):
        if len(addr) < 35 or len(addr) > 60:
            return False
        if addr != addr.lower() and addr != addr.upper():
            return False
        return all(c in BECH32_CHARSET for c in addr.lower())
    if addr.startswith("1") or addr.startswith("3"):
        return is_valid_btc_address(addr)
    return False

def is_valid_ada_address(addr: str) -> bool:
    """Validate Cardano address (Bech32 format). Supports mainnet and testnet."""
    if not addr:
        return False
    # Cardano Bech32 prefixes with HRP separator '1'
    # Format: HRP + '1' + data + checksum
    # Mainnet: addr1... / stake1...
    # Testnet: addr_test1... / stake_test1...
    if addr.startswith(("addr1", "stake1")):
        # Mainnet: check data part after HRP separator '1'
        # Find the separator '1' after the HRP
        hrp_end = addr.find('1', 4)  # after 'addr' or 'stake'
        if hrp_end == -1:
            return False
        data_part = addr[hrp_end + 1:]  # after the separator '1'
        return 45 <= len(data_part) <= 115 and all(c in BECH32_CHARSET for c in data_part.lower())
    if addr.startswith(("addr_test1", "stake_test1")):
        # Testnet: check data part after HRP separator '1'
        hrp_end = addr.find('1', 8)  # after 'addr_test' or 'stake_test'
        if hrp_end == -1:
            return False
        data_part = addr[hrp_end + 1:]
        return 45 <= len(data_part) <= 115 and all(c in BECH32_CHARSET for c in data_part.lower())
    return False


def validate_address(addr: str, chain: str) -> tuple[bool, str]:
    """Returns (is_valid, error_message)."""
    validators = {
        "btc": (is_valid_btc_address, _btc_validation_error(addr)),
        "eth": (is_valid_eth_address, "Debe ser 0x seguido de 40 caracteres hex (a-f, 0-9)."),
        "bch": (is_valid_bch_address, "Debe ser cashaddr (q/p...) o legacy (1/3...)."),
        "trx": (is_valid_trx_address, "Debe comenzar con T y tener 34 caracteres base58."),
        "ada": (is_valid_ada_address, "Debe ser addr1... (pago) o stake1... (stake) para mainnet, o addr_test1.../stake_test1... para testnet."),
    }
    validator, hint = validators.get(chain, (lambda a: bool(a), ""))
    if not validator(addr):
        return False, f"Dirección {chain.upper()} inválida. {hint}"
    return True, ""

# -------------------------
# Config
# -------------------------
NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASS = os.environ.get("NEO4J_PASSWORD", "neo4jneo4j")
NEO4J_DB = os.environ.get("NEO4J_DB", "")

AI_PROVIDER = os.environ.get("AI_PROVIDER", "ollama")
AI_MODEL = os.environ.get("AI_MODEL", "llama3" if AI_PROVIDER == "ollama" else "google/gemini-2.0-flash-001")
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")

TRACER_PARAMS = {
    "neo4j_uri": NEO4J_URI,
    "neo4j_user": NEO4J_USER,
    "neo4j_password": NEO4J_PASS,
    "verbose": True,
    "max_hops": int(os.environ.get("MAX_HOPS", "2")),
    "ai_provider": AI_PROVIDER,
    "ai_model": AI_MODEL,
    "chain": "btc",
}

OLLAMA_MODEL = AI_MODEL

# -------------------------
# Styling
# -------------------------
st.set_page_config(page_title="HOPS — Blockchain Forensics Platform", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    .stApp {
        background: #0f1117;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #161822 0%, #0f1117 100%);
        border-right: 1px solid rgba(255,255,255,0.06);
    }
    section[data-testid="stSidebar"] .stButton button {
        width: 100%;
        border-radius: 8px;
        font-weight: 600;
        font-size: 14px;
        padding: 10px 16px;
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
        border: none;
        color: white;
        transition: all 0.2s;
    }
    section[data-testid="stSidebar"] .stButton button:hover {
        transform: translateY(-1px);
        box-shadow: 0 8px 25px rgba(99,102,241,0.35);
    }
    section[data-testid="stSidebar"] .stSelectbox label {
        color: #94a3b8 !important;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-weight: 600;
    }

    /* Logo area */
    .sidebar-logo {
        padding: 24px 16px 16px;
        text-align: center;
        border-bottom: 1px solid rgba(255,255,255,0.06);
        margin-bottom: 20px;
    }
    .sidebar-logo img {
        max-width: 140px;
        height: auto;
    }
    .sidebar-brand {
        font-size: 22px;
        font-weight: 800;
        color: #e2e8f0;
        letter-spacing: -0.02em;
        margin-top: 8px;
    }
    .sidebar-brand span {
        background: linear-gradient(135deg, #6366f1, #a78bfa);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .sidebar-tagline {
        font-size: 11px;
        color: #64748b;
        margin-top: 2px;
        letter-spacing: 0.03em;
    }
    .sidebar-footer {
        position: fixed;
        bottom: 16px;
        left: 16px;
        right: 16px;
        font-size: 10px;
        color: #334155;
        text-align: center;
    }

    /* Main header */
    .main-header {
        padding: 8px 0 0;
    }
    .main-header h1 {
        font-size: 28px;
        font-weight: 800;
        color: #e2e8f0;
        letter-spacing: -0.03em;
        margin: 0;
    }
    .main-header p {
        color: #64748b;
        font-size: 14px;
        margin-top: 4px;
    }

    /* Filter card */
    .filter-card {
        background: #1a1d2e;
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 12px;
        padding: 20px 24px;
        margin: 16px 0 24px;
    }
    .filter-card h3 {
        color: #94a3b8;
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-weight: 600;
        margin: 0 0 16px;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        background: #1a1d2e;
        border-radius: 10px;
        padding: 4px;
        border: 1px solid rgba(255,255,255,0.06);
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        padding: 8px 18px;
        font-size: 13px;
        font-weight: 500;
        color: #64748b;
        transition: all 0.15s;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
        color: white !important;
        font-weight: 600;
    }

    /* Cards */
    .metric-card {
        background: #1a1d2e;
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 10px;
        padding: 16px 20px;
        transition: all 0.2s;
        position: relative;
    }
    .metric-card:hover {
        border-color: rgba(99,102,241,0.3);
    }
    .metric-card .label {
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #64748b;
        font-weight: 600;
        display: flex;
        align-items: center;
        gap: 4px;
    }
    .metric-card .value {
        font-size: 22px;
        font-weight: 700;
        color: #e2e8f0;
        margin-top: 4px;
    }

    /* Tooltip for risk panel */
    .tooltip {
        position: relative;
        cursor: help;
        font-size: 10px;
        color: #6366f1;
        margin-left: 4px;
    }
    .tooltip::after {
        content: attr(title);
        position: absolute;
        bottom: 125%;
        left: 50%;
        transform: translateX(-50%);
        background: #1e293b;
        color: #e2e8f0;
        padding: 10px 14px;
        border-radius: 6px;
        font-size: 11px;
        font-weight: 400;
        white-space: pre-line;
        width: max-content;
        max-width: 320px;
        opacity: 0;
        visibility: hidden;
        transition: all 0.2s;
        z-index: 100;
        border: 1px solid rgba(99,102,241,0.3);
        box-shadow: 0 10px 25px rgba(0,0,0,0.3);
        text-transform: none;
        letter-spacing: normal;
        font-weight: 400;
    }
    .tooltip::before {
        content: '';
        position: absolute;
        top: 100%;
        left: 50%;
        transform: translateX(-50%);
        border: 6px solid transparent;
        border-top-color: #1e293b;
        opacity: 0;
        visibility: hidden;
        transition: all 0.2s;
    }
    .tooltip:hover::after,
    .tooltip:hover::before {
        opacity: 1;
        visibility: visible;
    }

    /* Report section */
    .report-section {
        background: #1a1d2e;
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 12px;
        padding: 24px;
        margin-top: 16px;
    }

    /* Download buttons */
    .stDownloadButton button {
        border-radius: 8px;
        font-weight: 600;
        font-size: 13px;
        padding: 8px 20px;
        transition: all 0.2s;
    }

    /* Success/warning/info boxes */
    .stAlert {
        border-radius: 10px;
        border: none;
    }

    /* DataFrames */
    .stDataFrame {
        border-radius: 10px;
        overflow: hidden;
    }

    /* Text inputs */
    .stTextInput input {
        border-radius: 10px;
        border: 1px solid rgba(255,255,255,0.1);
        background: #1a1d2e;
        color: #e2e8f0;
        font-size: 15px;
        padding: 12px 16px;
    }
    .stTextInput input:focus {
        border-color: #6366f1;
        box-shadow: 0 0 0 3px rgba(99,102,241,0.15);
    }

    /* Checkboxes */
    .stCheckbox label {
        color: #cbd5e1 !important;
        font-size: 13px;
    }

    /* Number inputs */
    .stNumberInput input {
        border-radius: 8px;
        border: 1px solid rgba(255,255,255,0.1);
        background: #1a1d2e;
        color: #e2e8f0;
    }

    /* Select boxes in filters */
    .stSelectbox div[data-baseweb="select"] {
        border-radius: 8px;
        border: 1px solid rgba(255,255,255,0.1);
        background: #1a1d2e;
    }

    hr {
        border-color: rgba(255,255,255,0.06);
        margin: 12px 0;
    }

    /* Spinner */
    .stSpinner > div {
        border-color: #6366f1 !important;
    }

    /* Markdown text */
    p, li, .stMarkdown {
        color: #cbd5e1;
    }
    h1, h2, h3, h4, h5, h6 {
        color: #e2e8f0;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------
# Neo4j helpers
# -------------------------
def get_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))

def address_exists(addr, chain="btc"):
    driver = get_driver()
    try:
        with driver.session() as s:
            r = s.run(
                "MATCH (a:Address {address:$a}) WHERE a.chain IS NULL OR a.chain = $chain RETURN a LIMIT 1",
                a=addr, chain=chain,
            ).single()
        return r is not None
    finally:
        driver.close()

def address_has_relations(addr, chain="btc"):
    driver = get_driver()
    try:
        with driver.session() as s:
            r = s.run(
                "MATCH (a:Address {address:$a}) WHERE a.chain IS NULL OR a.chain = $chain MATCH (a)-[r:SENT]-() RETURN count(r) AS cnt",
                a=addr, chain=chain,
            ).single()
        return r is not None and r["cnt"] > 0
    finally:
        driver.close()

def fetch_subgraph(addr, depth=2, limit=5000, chain="btc"):
    driver = get_driver()
    depth_literal = f"*1..{int(depth)}"

    q = f"""
    MATCH (root:Address {{address:$addr}})
    WHERE root.chain IS NULL OR root.chain = $chain
    MATCH p=(root)-[:SENT{depth_literal}]-(b:Address)
    UNWIND relationships(p) AS rel
    WITH DISTINCT rel
    MATCH (a:Address)-[rel]->(b:Address)
    WHERE (a.chain IS NULL OR a.chain = $chain) AND (b.chain IS NULL OR b.chain = $chain)
    RETURN 
        a.address AS from_addr,
        b.address AS to_addr,
        rel.amount AS amount,
        rel.txid AS txid,
        coalesce(rel.hop, 1) AS hop,
        coalesce(rel.block_time, rel.timestamp) AS ts,
        coalesce(rel.is_change, false) AS is_change,
        a.entity_type AS from_entity,
        b.entity_type AS to_entity,
        a.labels AS from_labels,
        b.labels AS to_labels
    LIMIT $limit
    """

    rows = []
    try:
        with driver.session() as s:
            for rec in s.run(q, addr=addr, limit=limit, chain=chain):
                row = dict(rec)
                if not isinstance(row.get('from_labels'), list):
                    row['from_labels'] = []
                if not isinstance(row.get('to_labels'), list):
                    row['to_labels'] = []

                ts = row.get('ts')
                if ts:
                    if hasattr(ts, 'to_native'):
                        ts = ts.to_native()
                    if hasattr(ts, 'timestamp'):
                        ts = ts.timestamp()
                    try:
                        row['ts'] = int(float(ts))
                    except (ValueError, TypeError):
                        row['ts'] = 0
                else:
                    row['ts'] = 0

                rows.append(row)
        return rows
    finally:
        driver.close()

# -------------------------
# Graph
# -------------------------
GRAPH_ENTITY_COLORS = {
    "exchange": "#3b82f6",
    "mixer": "#ef4444",
    "sanctioned": "#b91c1c",
    "darknet_market": "#7f1d1d",
    "darkmarket": "#7f1d1d",
    "gambling": "#f59e0b",
    "bridge": "#22c55e",
    "wallet_service": "#06b6d4",
    "mining_pool": "#8b5cf6",
    "defi_protocol": "#14b8a6",
    "marketplace": "#f97316",
    "individual": "#6b7280",
    "unknown": "#6b7280",
    "other": "#6b7280",
    None: "#6b7280",
}
GRAPH_ROOT_COLOR = "#fbbf24"
GRAPH_HIGH_RISK_ENTITIES = {"mixer", "sanctioned", "darknet_market", "darkmarket"}


def _fmt_labels(labels):
    if isinstance(labels, list):
        labels = ", ".join(labels)
    return html.escape(str(labels)) if labels else ""


def show_graph(edges, root_addr=None, unit="BTC"):
    if not edges:
        st.info("Sin datos para grafo.")
        return

    net = Network(height="650px", width="100%", directed=True, bgcolor="#1a1d2e", font_color="white")

    # Total volume per node, used to scale node size (bigger node = more funds through it).
    node_volume = {}
    for e in edges:
        amt = float(e.get("amount") or 0)
        node_volume[e["from_addr"]] = node_volume.get(e["from_addr"], 0.0) + amt
        node_volume[e["to_addr"]] = node_volume.get(e["to_addr"], 0.0) + amt
    max_volume = max(node_volume.values()) if node_volume else 1.0
    max_amount = max((float(e.get("amount") or 0) for e in edges), default=1.0) or 1.0

    def node_size(addr):
        if addr == root_addr:
            return 42
        vol = node_volume.get(addr, 0.0)
        return 14 + 26 * ((vol / max_volume) ** 0.5 if max_volume else 0)

    def add_node(addr, entity, labels):
        if addr in added_nodes:
            return
        added_nodes.add(addr)
        is_root = addr == root_addr
        is_high_risk = entity in GRAPH_HIGH_RISK_ENTITIES
        label_text = _fmt_labels(labels)
        tooltip = (
            f"<b>{html.escape(addr)}</b><br>"
            f"Entidad: {html.escape(str(entity or 'unknown'))}<br>"
            f"Volumen total: {node_volume.get(addr, 0.0):.8f} {unit}"
        )
        if label_text:
            tooltip += f"<br>Etiquetas: {label_text}"
        if is_root:
            tooltip += "<br><b>&#128204; Direccion analizada</b>"

        net.add_node(
            addr,
            label=("\U0001F3AF " if is_root else "") + addr[:12] + "...",
            title=tooltip,
            color={
                "background": GRAPH_ROOT_COLOR if is_root else GRAPH_ENTITY_COLORS.get(entity, "#6b7280"),
                "border": "#fef3c7" if is_root else ("#f87171" if is_high_risk else "#1a1d2e"),
            },
            borderWidth=4 if (is_root or is_high_risk) else 1,
            size=node_size(addr),
            shape="dot",
        )

    added_nodes = set()
    for e in edges:
        add_node(e["from_addr"], e.get("from_entity"), e.get("from_labels"))
        add_node(e["to_addr"], e.get("to_entity"), e.get("to_labels"))

        amt = float(e.get("amount") or 0)
        width = 1 + 7 * (amt / max_amount)
        ts = e.get("ts")
        date_str = datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M") if ts else "?"
        txid = e.get("txid") or ""
        edge_tooltip = (
            f"Monto: {amt:.8f} {unit}<br>"
            f"Fecha: {date_str} UTC<br>"
            f"Hop: {e.get('hop', '?')}<br>"
            f"TX: {html.escape(txid[:24])}..."
        )
        net.add_edge(
            e["from_addr"], e["to_addr"],
            value=amt, width=width, title=edge_tooltip,
            color={"color": "#4b5563", "highlight": "#fbbf24", "hover": "#9ca3af"},
            arrowStrikethrough=False,
        )

    net.set_options("""
    {
      "physics": {"solver": "forceAtlas2Based", "forceAtlas2Based": {"gravitationalConstant": -60, "centralGravity": 0.008, "springLength": 160, "avoidOverlap": 0.6}, "stabilization": {"iterations": 150}},
      "edges": {"smooth": {"type": "dynamic"}, "arrows": {"to": {"enabled": true, "scaleFactor": 0.5}}},
      "interaction": {"hover": true, "tooltipDelay": 100, "navigationButtons": true, "keyboard": true}
    }
    """)

    # Unique filename avoids collisions between concurrent Streamlit sessions
    # viewing different addresses at the same time.
    graph_file = os.path.join(tempfile.gettempdir(), f"hops_graph_{uuid.uuid4().hex}.html")
    try:
        net.save_graph(graph_file)
        with open(graph_file, "r", encoding="utf-8") as f:
            graph_html = f.read()
    finally:
        if os.path.exists(graph_file):
            os.remove(graph_file)

    html_base64 = base64.b64encode(graph_html.encode('utf-8')).decode('utf-8')
    iframe_src = f"data:text/html;base64,{html_base64}"

    legend_items = [
        ("Direccion analizada", GRAPH_ROOT_COLOR),
        ("Exchange", GRAPH_ENTITY_COLORS["exchange"]),
        ("Mixer", GRAPH_ENTITY_COLORS["mixer"]),
        ("Sancionado / Darknet", GRAPH_ENTITY_COLORS["sanctioned"]),
        ("Bridge", GRAPH_ENTITY_COLORS["bridge"]),
        ("Gambling", GRAPH_ENTITY_COLORS["gambling"]),
        ("Wallet service", GRAPH_ENTITY_COLORS["wallet_service"]),
        ("Desconocido / individual", GRAPH_ENTITY_COLORS["unknown"]),
    ]
    legend_html = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:6px;margin-right:16px;font-size:12px;color:#d1d5db;">'
        f'<span style="width:12px;height:12px;border-radius:50%;background:{color};display:inline-block;"></span>{label}</span>'
        for label, color in legend_items
    )
    st.markdown(
        f'<div style="margin-bottom:8px;">{legend_html}</div>',
        unsafe_allow_html=True,
    )
    st.caption("El tamaño del nodo refleja el volumen total que pasa por esa dirección. El grosor de la arista refleja el monto de la transacción. Pase el cursor sobre nodos y aristas para ver detalles.")

    st.markdown(
        f'<iframe src="{iframe_src}" width="100%" height="650" style="border:none; border-radius: 10px;"></iframe>',
        unsafe_allow_html=True
    )

# -------------------------
# Sankey
# -------------------------
def show_sankey(edges):
    if not edges:
        st.info("Sin datos para Sankey.")
        return

    df = pd.DataFrame(edges)
    df = df[df["amount"].notnull()]
    if df.empty:
        st.info("Sin datos válidos para Sankey.")
        return

    df["from_entity"] = df.get("from_entity", None).fillna("unknown")
    df["to_entity"] = df.get("to_entity", None).fillna("unknown")
    df["amount"] = df["amount"].astype(float)
    top = (
        df.groupby(["from_addr", "to_addr", "from_entity", "to_entity"], as_index=False)
        .sum()
        .sort_values("amount", ascending=False)
        .head(200)
    )
    st.dataframe(top, use_container_width=True)

# -------------------------
# Heatmap
# -------------------------
def show_heatmap(edges):
    if not edges:
        st.info("Sin datos para Heatmap.")
        return

    df = pd.DataFrame(edges)
    df = df[df["amount"].notnull()]
    if df.empty:
        st.info("Sin datos válidos para Heatmap.")
        return

    df["hour"] = pd.to_datetime(df["ts"], unit="s").dt.hour
    agg = df.groupby("hour").amount.sum().reset_index()
    chart = alt.Chart(agg).mark_bar(color="#6366f1").encode(x="hour:O", y="amount:Q")
    st.altair_chart(chart, use_container_width=True)

# -------------------------
# Timeline
# -------------------------
def show_timeline(edges):
    if not edges:
        st.info("Sin datos para Timeline.")
        return

    df = pd.DataFrame(edges)
    df = df[df["amount"].notnull()]
    if df.empty:
        st.info("Sin datos válidos para Timeline.")
        return

    df["time"] = pd.to_datetime(df["ts"], unit="s")
    df = df.sort_values("time")
    chart = alt.Chart(df).mark_line(color="#6366f1").encode(x="time:T", y="amount:Q")
    st.altair_chart(chart, use_container_width=True)

# -------------------------
# Risk panel
# -------------------------
def show_risk(edges, root, chain="btc"):
    if not edges:
        st.info("Sin datos para panel de riesgo.")
        return

    unit = {"btc": "BTC", "eth": "ETH", "bch": "BCH", "trx": "TRX", "ada": "ADA"}.get(chain, "BTC")
    df = pd.DataFrame(edges)
    df = df[df["amount"].notnull()]
    if df.empty:
        st.info("Sin datos válidos para riesgo.")
        return

    df["amount"] = df["amount"].astype(float)
    total_in = df[df["to_addr"] == root]["amount"].sum()
    total_out = df[df["from_addr"] == root]["amount"].sum()
    neighbors = pd.concat([df["from_addr"], df["to_addr"]]).nunique()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="label">Total entrante</div>
            <div class="value">{total_in:.8f} {unit}</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="label">Total saliente <span class="tooltip" title="El total saliente puede ser mayor que el entrante porque:
• El análisis tiene profundidad limitada (N hops)
• Cambios (change) en modelo UTXO (BTC, ADA, BCH)
• Direcciones de cambio distintas
• Saldo previo no rastreado
• Filtrado de transacciones pequeñas">ℹ️</span></div>
            <div class="value">{total_out:.8f} {unit}</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="label">Vecinos únicos</div>
            <div class="value">{neighbors}</div>
        </div>
        """, unsafe_allow_html=True)

# -------------------------
# Main dashboard
# -------------------------
def show_dashboard(addr, filters, chain="btc"):
    edges = fetch_subgraph(addr, depth=TRACER_PARAMS["max_hops"], chain=chain)
    edges = [e for e in edges if "amount" in e and e["amount"] is not None]

    if not edges:
        st.warning("No hay relaciones válidas para esta dirección.")
        return

    edges = [e for e in edges if float(e["amount"]) >= filters["min_amount"]]
    if filters["only_hop1"]:
        edges = [e for e in edges if e.get("hop") == 1]
    if filters["only_fanin"]:
        edges = [e for e in edges if e.get("to_addr") == addr]
    if filters["only_fanout"]:
        # Mirrors the "only_fanin" filter above: an edge only qualifies as
        # fan-out if it directly originates from the analyzed address.
        # (hop > 1 edges are between two *other* addresses and are neither
        # fan-in nor fan-out of `addr` — including them here previously let
        # almost every hop>=2 edge through regardless of direction.)
        edges = [e for e in edges if e.get("from_addr") == addr]
    if filters["hide_change"]:
        edges = [e for e in edges if not e.get("is_change", False)]
    if filters["entity"] != "Todas":
        edges = [
            e for e in edges
            if e.get("from_entity") == filters["entity"] or e.get("to_entity") == filters["entity"]
        ]

    if not edges:
        st.warning("Tras aplicar filtros no quedan relaciones.")
        return

    unit = {"btc": "BTC", "eth": "ETH", "bch": "BCH", "trx": "TRX", "ada": "ADA"}.get(chain, "BTC")

    tabs = st.tabs(["Grafo", "Sankey", "Heatmap", "Timeline", "Tabla", "Riesgo", "Reporte IA", "Grafo Detallado"])

    with tabs[0]:
        show_graph(edges, root_addr=addr, unit=unit)

    with tabs[1]:
        show_sankey(edges)

    with tabs[2]:
        show_heatmap(edges)

    with tabs[3]:
        show_timeline(edges)

    with tabs[4]:
        df = pd.DataFrame(edges)
        if "ts" in df.columns:
            df["time"] = pd.to_datetime(df["ts"], unit="s")
            df = df.sort_values("time")
        def _labels_to_str(labels):
            if isinstance(labels, list):
                return ', '.join(labels)
            elif isinstance(labels, str):
                return labels
            else:
                return str(labels) if labels else ''
        if 'from_labels' in df.columns:
            df['from_label'] = df['from_labels'].apply(_labels_to_str)
        if 'to_labels' in df.columns:
            df['to_label'] = df['to_labels'].apply(_labels_to_str)
        display_columns = ['from_addr', 'to_addr', 'amount', 'txid', 'hop', 'ts', 'is_change', 'from_label', 'to_label', 'time']
        display_columns = [col for col in display_columns if col in df.columns]
        st.dataframe(df[display_columns], use_container_width=True)

    with tabs[5]:
        show_risk(edges, addr, chain=chain)

    # -------------------------
    # AI Report tab
    # -------------------------
    with tabs[6]:
        col_legacy, col_enhanced = st.columns(2)
        with col_legacy:
            if st.button("Generar reporte IA (simple)", use_container_width=True):
                tracer = BTCForensicsPro(**TRACER_PARAMS, min_amount=filters["min_amount"])
                resumen = tracer.build_summary(st.session_state.last_address)
                reporte = tracer.generate_ai_report_with_ollama(resumen, model=OLLAMA_MODEL)
                st.session_state.ai_report = reporte
                st.session_state.transaction_graph = tracer.generate_transaction_graph_html(
                    st.session_state.last_address, limit=100
                )
                paths = tracer.save_report_to_files(st.session_state.last_address, reporte)
                metadata = {
                    "model": OLLAMA_MODEL,
                    "generated_at": int(time.time()),
                    "filters": filters
                }
                tracer.save_report_to_neo4j(st.session_state.last_address, reporte, model=OLLAMA_MODEL, metadata=metadata)
                tracer.close()
                st.success("Reporte simple generado.")

        with col_enhanced:
            if st.button("Generar reporte IA + PDF (completo)", use_container_width=True):
                with st.spinner("Generando reporte completo..."):
                    tracer = BTCForensicsPro(**TRACER_PARAMS, min_amount=filters["min_amount"])
                    result = tracer.generate_enhanced_report(
                        st.session_state.last_address,
                        filters=filters,
                        depth=TRACER_PARAMS["max_hops"],
                        model=OLLAMA_MODEL,
                    )
                    if "error" in result:
                        st.error(result["error"])
                    else:
                        st.session_state.enhanced_report = result
                        metadata_path = result.get("data_json", "")
                        if metadata_path and os.path.exists(metadata_path):
                            with open(metadata_path, "r", encoding="utf-8") as f:
                                meta = json.load(f)
                            st.session_state.ai_report = meta.get("ollama_narrative", "")
                        else:
                            st.session_state.ai_report = result.get("ollama_narrative", "")
                        st.session_state.transaction_graph = result.get("graph")
                    tracer.close()

        st.markdown("---")
        col_pericial, col_compliance = st.columns(2)
        with col_pericial:
            with st.expander("⚖️ Datos del caso para Informe Pericial", expanded=False):
                victim = st.text_input("Nombre de la víctima", placeholder="ej: Juan Pérez", key="pericial_victim")
                case_num = st.text_input("Nº de diligencias / procedimiento", placeholder="ej: DP 1234/2024", key="pericial_case")
                court = st.text_input("Juzgado instructor", placeholder="ej: Juzgado de Instrucción nº 5 de Madrid", key="pericial_court")
                txhash = st.text_input("Hash de transacción inicial (opcional)", placeholder="ej: 0x...", key="pericial_txhash")
                notes = st.text_area("Notas adicionales (opcional)", placeholder="Contexto del caso...", key="pericial_notes", height=80)

            if st.button("⚖️ Generar Informe Pericial", use_container_width=True, type="primary"):
                if not victim:
                    st.warning("Ingresa al menos el nombre de la víctima para el informe pericial.")
                else:
                    with st.spinner("Generando informe pericial..."):
                        case_data = {
                            "Nombre de la victima": victim,
                            "Numero de diligencias": case_num,
                            "Juzgado instructor": court,
                            "Hash de transaccion inicial": txhash,
                            "Notas adicionales": notes,
                        }
                        tracer = BTCForensicsPro(**TRACER_PARAMS, min_amount=filters["min_amount"])
                        result = tracer.generate_forensic_pericial_report(
                            st.session_state.last_address,
                            filters=filters,
                            depth=TRACER_PARAMS["max_hops"],
                            model=OLLAMA_MODEL,
                            case_data=case_data,
                        )
                        if "error" in result:
                            st.error(result["error"])
                        else:
                            st.session_state.pericial_report = result
                            metadata_path = result.get("data_json", "")
                            if metadata_path and os.path.exists(metadata_path):
                                with open(metadata_path, "r", encoding="utf-8") as f:
                                    meta = json.load(f)
                                st.session_state.ai_report = meta.get("ollama_narrative", "")
                            else:
                                st.session_state.ai_report = result.get("ollama_narrative", "")
                            st.session_state.transaction_graph = result.get("graph")
                            st.success("Informe Pericial generado exitosamente!")
                        tracer.close()

        with col_compliance:
            st.info("🔒 Informe Compliance — próximamente")
            st.button("Generar Informe Compliance", disabled=True, use_container_width=True)

        # Display AI narrative if generated by any report
        if st.session_state.ai_report:
            st.markdown("""
            <div class="report-section">
                <h4 style="color:#e2e8f0; margin: 0 0 12px; font-size: 15px; font-weight: 600;">📄 Reporte generado</h4>
            </div>
            """, unsafe_allow_html=True)
            st.write(st.session_state.ai_report)

        # Download section for enhanced/pericial reports
        report_result = st.session_state.get("enhanced_report") or st.session_state.get("pericial_report")
        if report_result:
            st.markdown("---")
            st.success("Reporte completo generado exitosamente!")

            folder = report_result.get("folder", "")
            pdf_path = report_result.get("pdf", "")
            html_path = report_result.get("html", "")

            if folder:
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    if pdf_path and os.path.exists(pdf_path):
                        with open(pdf_path, "rb") as f:
                            st.download_button(
                                label="📥 Descargar PDF",
                                data=f,
                                file_name=os.path.basename(pdf_path),
                                mime="application/pdf",
                                use_container_width=True,
                            )
                    else:
                        pdf_error = report_result.get("pdf_error", "")
                        msg = "PDF no disponible"
                        if pdf_error:
                            msg += f": {pdf_error}"
                        st.warning(msg)

                with col_b:
                    if html_path and os.path.exists(html_path):
                        with open(html_path, "r", encoding="utf-8") as f:
                            st.download_button(
                                label="📥 Descargar HTML",
                                data=f,
                                file_name=os.path.basename(html_path),
                                mime="text/html",
                                use_container_width=True,
                            )

                with col_c:
                    csv_path = report_result.get("transactions_csv", "")
                    if csv_path and os.path.exists(csv_path):
                        with open(csv_path, "r", encoding="utf-8") as f:
                            st.download_button(
                                label="📥 Descargar CSV",
                                data=f,
                                file_name=os.path.basename(csv_path),
                                mime="text/csv",
                                use_container_width=True,
                            )

                st.markdown("---")
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                    for fname in sorted(os.listdir(folder)):
                        fpath = os.path.join(folder, fname)
                        if os.path.isfile(fpath):
                            zf.write(fpath, arcname=fname)
                zip_buffer.seek(0)
                st.download_button(
                    label="📦 Descargar todo (ZIP)",
                    data=zip_buffer,
                    file_name=f"reporte_{st.session_state.last_address[:12]}.zip",
                    mime="application/zip",
                    type="primary",
                    use_container_width=True,
                )

                if os.path.exists(folder):
                    with st.expander("Archivos generados", expanded=True):
                        for fname in sorted(os.listdir(folder)):
                            fpath = os.path.join(folder, fname)
                            size = os.path.getsize(fpath)
                            st.text(f"  {fname} ({size:,} bytes)")

    with tabs[7]:
        if st.session_state.transaction_graph:
            st.markdown("""
            <h4 style="color:#e2e8f0; margin-bottom: 12px; font-weight: 600;">Grafo de Transacciones Detallado</h4>
            """, unsafe_allow_html=True)
            st.components.v1.html(st.session_state.transaction_graph, height=750, scrolling=True)
        else:
            st.info("Presione 'Generar reporte IA + PDF' en la pestaña 'Reporte IA' para construir y visualizar el grafo interactivo.")

# -------------------------
# Main UI
# -------------------------
def main():
    # Sidebar
    with st.sidebar:
        st.markdown("""
        <div class="sidebar-logo">
            <img src="data:image/png;base64,{0}" width="140">
            <div class="sidebar-brand">HOPS <span>Forensics</span></div>
            <div class="sidebar-tagline">Blockchain Intelligence Platform</div>
        </div>
        """.format(_get_logo_b64()), unsafe_allow_html=True)

        chain = st.selectbox("Red", ["BTC", "ETH", "BCH", "TRX", "ADA"], index=0, label_visibility="collapsed")
        chain = chain.lower()
        unit = {"btc": "BTC", "eth": "ETH", "bch": "BCH", "trx": "TRX", "ada": "ADA"}.get(chain, "BTC")
        TRACER_PARAMS["chain"] = chain

        max_hops = st.slider("Profundidad (hops)", min_value=1, max_value=5, value=min(TRACER_PARAMS["max_hops"], 5), help="A mayor profundidad, más llamadas a APIs externas y mayor tiempo de procesamiento.")
        TRACER_PARAMS["max_hops"] = max_hops

        st.markdown("<hr style='margin: 20px 0 12px;'>", unsafe_allow_html=True)

        # -------------------------
        # Label editor in sidebar
        # -------------------------
        with st.expander("🏷️ Editar etiquetas", expanded=False):
            search_addr = st.text_input("Buscar dirección", placeholder="Dirección completa o parcial...", label_visibility="collapsed")
            if search_addr:
                driver = get_driver()
                try:
                    with driver.session() as s:
                        results = list(s.run("""
                            MATCH (a:Address)
                            WHERE a.address CONTAINS $q OR ANY(lab IN a.labels WHERE lab CONTAINS $q)
                            RETURN a.address AS address, a.chain AS chain,
                                   a.entity_type AS entity_type, a.labels AS labels,
                                   a.wallet_id AS wallet_id
                            LIMIT 15
                        """, q=search_addr))
                finally:
                    driver.close()
                if results:
                    for rec in results:
                        addr = rec["address"]
                        cur_labels = rec["labels"] or []
                        cur_entity = rec["entity_type"] or "unknown"
                        st.caption(f"`{addr[:20]}...` ({rec['chain'] or '?'})")
                        cols = st.columns([3, 1])
                        with cols[0]:
                            new_labels = st.text_input("Labels", value=", ".join(cur_labels) if cur_labels else "",
                                                       key=f"lbl_{addr}", label_visibility="collapsed",
                                                       placeholder="label1, label2")
                        with cols[1]:
                            new_entity = st.selectbox("Tipo", ["unknown", "exchange", "mixer", "sanctioned", "bridge", "gambling", "ransomware", "darkweb", "darkmarket", "other"],
                                                      index=["unknown", "exchange", "mixer", "sanctioned", "bridge", "gambling", "ransomware", "darkweb", "darkmarket", "other"].index(cur_entity) if cur_entity in ["unknown", "exchange", "mixer", "sanctioned", "bridge", "gambling", "ransomware", "darkweb", "darkmarket", "other"] else 0,
                                                      key=f"ent_{addr}", label_visibility="collapsed")
                        if st.button("Guardar", key=f"save_{addr}", use_container_width=True):
                            parsed = [x.strip() for x in new_labels.split(",") if x.strip()]
                            parsed = list(dict.fromkeys(parsed))
                            driver2 = get_driver()
                            try:
                                with driver2.session() as s2:
                                    s2.run("""
                                        MATCH (a:Address {address: $addr})
                                        SET a.labels = $labels,
                                            a.entity_type = $entity_type,
                                            a.updated_at = datetime()
                                    """, addr=addr, labels=parsed, entity_type=new_entity)
                            finally:
                                driver2.close()
                            st.success(f"✓ {addr[:16]}...")
                            st.rerun()
                        st.divider()
                else:
                    st.info("Sin resultados.")

        st.markdown("""
        <div class="sidebar-footer">
            HOPS v2.0 — Labmoon © 2026
        </div>
        """, unsafe_allow_html=True)

    # Main content
    st.markdown('<div class="main-header">', unsafe_allow_html=True)
    st.markdown(f"""
    <h1>🔍 Análisis Forense {unit.upper()}</h1>
    <p>Ingrese una dirección de {unit.upper()} para trazar transacciones, detectar patrones y generar reportes de inteligencia.</p>
    """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Session state
    if "analysis_done" not in st.session_state:
        st.session_state.analysis_done = False
    if "last_address" not in st.session_state:
        st.session_state.last_address = None
    if "ai_report" not in st.session_state:
        st.session_state.ai_report = None
    if "transaction_graph" not in st.session_state:
        st.session_state.transaction_graph = None
    if "enhanced_report" not in st.session_state:
        st.session_state.enhanced_report = None
    if "chain" not in st.session_state:
        st.session_state.chain = chain

    # Address input
    addr_input = st.text_input(
        f"Dirección {unit}",
        value=st.session_state.last_address or "",
        placeholder=f"Ingrese una dirección de {unit.upper()}...",
        label_visibility="collapsed",
    )
    addr = addr_input.strip()

    # Filters
    st.markdown('<div class="filter-card"><h3>⚙️ Filtros de análisis</h3>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        min_amount = st.number_input(f"Monto mínimo ({unit})", min_value=0.0, value=0.00001, step=0.00001, format="%.8f")
    with col2:
        only_hop1 = st.checkbox("Solo hop 1")
        only_fanin = st.checkbox("Solo FAN-IN")
    with col3:
        hide_change = st.checkbox("Ocultar change outputs")
        only_fanout = st.checkbox("Solo FAN-OUT")

    # Date range filter
    col_date1, col_date2 = st.columns(2)
    with col_date1:
        start_date = st.date_input("Fecha inicio", value=None, format="YYYY-MM-DD")
    with col_date2:
        end_date = st.date_input("Fecha fin", value=None, format="YYYY-MM-DD")

    entity = st.selectbox("Filtrar por entidad", ["Todas", "exchange", "mixer", "bridge", "sanctioned", "other"], label_visibility="collapsed")
    st.markdown('</div>', unsafe_allow_html=True)

    filters = {
        "min_amount": min_amount,
        "only_hop1": only_hop1,
        "hide_change": hide_change,
        "only_fanin": only_fanin,
        "only_fanout": only_fanout,
        "entity": entity,
        "_chain": chain,
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
    }

    if st.button("Iniciar análisis", use_container_width=True):
        if not addr:
            st.error("Por favor ingrese una dirección válida.")
            return

        valid, err_msg = validate_address(addr, chain)
        if not valid:
            st.error(err_msg)
            return

        st.session_state.last_address = addr
        st.session_state.chain = chain
        st.session_state.ai_report = None

        tracer = BTCForensicsPro(**TRACER_PARAMS, min_amount=min_amount)
        try:
            if not address_has_relations(addr, chain=chain):
                # Progress container
                progress_placeholder = st.empty()
                progress_container = st.status("Iniciando rastreo...", expanded=True)

                def progress_callback(message: str):
                    progress_container.update(label=message, state="running")

                try:
                    ok = tracer.trace(addr, progress_callback=progress_callback)
                except Exception as e:
                    progress_container.update(label="Error durante el rastreo", state="error")
                    st.error(f"Ocurrió un error inesperado al rastrear {addr}: {e}")
                    return

                progress_container.update(label="¡Rastreo completado!", state="complete" if ok else "error")

                if not ok:
                    detail = getattr(tracer, '_last_trace_error', '')
                    msg = f"No se pudieron obtener transacciones para {addr} en {unit.upper()}."
                    if detail:
                        msg += f"\n\nDetalle: {detail}"
                    if chain == "eth":
                        msg += "\n\nVerifica que la dirección sea válida y que ETHERSCAN_API_KEY esté configurada."
                    elif chain == "bch":
                        msg += "\n\nVerifica que la dirección sea válida (usa formato legacy 1... o cashaddr q...)."
                    elif chain == "trx":
                        msg += "\n\nVerifica que la dirección sea válida (formato T...)."
                    else:
                        msg += "\n\nVerifica que la dirección sea válida."
                    st.error(msg)
                    return
            # Reached when tracing just completed successfully, OR when the
            # address already had relations in Neo4j from a previous run
            # (in which case tracing is skipped entirely and we go straight
            # to showing the existing data).
            st.session_state.analysis_done = True
        finally:
            tracer.close()

    if st.session_state.analysis_done and st.session_state.last_address:
        show_dashboard(st.session_state.last_address, filters, chain=chain)

def _get_logo_b64():
    try:
        logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
        if os.path.exists(logo_path):
            with open(logo_path, "rb") as f:
                return base64.b64encode(f.read()).decode()
    except Exception:
        pass
    return ""

if __name__ == "__main__":
    main()
