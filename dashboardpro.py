# dashboard.py
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
import os
import zipfile
import io
from pyvis.network import Network
import streamlit.components.v1 as components

# -------------------------
# Configuración (from env for Coolify)
# -------------------------
NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASS = os.environ.get("NEO4J_PASSWORD", "neo4jneo4j")
NEO4J_DB = os.environ.get("NEO4J_DB", "")

AI_PROVIDER = os.environ.get("AI_PROVIDER", "ollama")  # "ollama" or "openrouter"
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
# Neo4j helpers
# -------------------------
def get_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))

def address_exists(addr, chain="btc"):
    driver = get_driver()
    with driver.session() as s:
        r = s.run(
            "MATCH (a:Address {address:$a}) WHERE coalesce(a.chain, \"btc\") = $chain RETURN a LIMIT 1",
            a=addr, chain=chain,
        ).single()
    driver.close()
    return r is not None

def address_has_relations(addr, chain="btc"):
    driver = get_driver()
    with driver.session() as s:
        r = s.run(
            "MATCH (a:Address {address:$a}) WHERE coalesce(a.chain, \"btc\") = $chain MATCH (a)-[r:SENT]-() RETURN count(r) AS cnt",
            a=addr, chain=chain,
        ).single()
    driver.close()
    return r is not None and r["cnt"] > 0

def fetch_subgraph(addr, depth=2, limit=5000, chain="btc"):
    driver = get_driver()
    depth_literal = f"*1..{depth}"

    q = f"""
    MATCH (root:Address {{address:$addr}})
    WHERE coalesce(root.chain, "btc") = $chain
    MATCH p=(root)-[:SENT{depth_literal}]-(b:Address)
    UNWIND relationships(p) AS rel
    WITH DISTINCT rel
    MATCH (a:Address)-[rel]->(b:Address)
    WHERE coalesce(a.chain, "btc") = $chain AND coalesce(b.chain, "btc") = $chain
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
    with driver.session() as s:
        for rec in s.run(q, addr=addr, limit=limit, chain=chain):
            row = dict(rec)
            # Ensure labels are lists
            if not isinstance(row.get('from_labels'), list):
                row['from_labels'] = []
            if not isinstance(row.get('to_labels'), list):
                row['to_labels'] = []
            
            # Robust conversion of timestamp (ts) to epoch integer
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

    driver.close()
    return rows
def show_graph(edges):
    if not edges:
        st.info("Sin datos para grafo.")
        return

    net = Network(height="600px", width="100%", directed=True, bgcolor="#222222", font_color="white")

    color_map = {
        "exchange": "blue",
        "mixer": "red",
        "sanctioned": "black",
        "bridge": "green",
        "other": "gray",
        None: "gray"
    }

    for e in edges:
        fe = e.get("from_entity", "other")
        te = e.get("to_entity", "other")

        net.add_node(e["from_addr"], label=e["from_addr"][:12] + "...", color=color_map.get(fe, "gray"))
        net.add_node(e["to_addr"], label=e["to_addr"][:12] + "...", color=color_map.get(te, "gray"))

        net.add_edge(e["from_addr"], e["to_addr"], value=float(e["amount"]))

    net.repulsion(node_distance=180, central_gravity=0.33, spring_length=150)

    net.save_graph("graph.html")

    with open("graph.html", "r", encoding="utf-8") as f:
        html = f.read()
    
    # Encode HTML to base64 for iframe srcdoc
    html_base64 = base64.b64encode(html.encode('utf-8')).decode('utf-8')
    iframe_src = f"data:text/html;base64,{html_base64}"
    
    # Display using iframe
    st.markdown(
        f'<iframe src="{iframe_src}" width="100%" height="600" style="border:none;"></iframe>',
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

    df["amount"] = df["amount"].astype(float)
    top = (
        df.groupby(["from_addr", "to_addr"], as_index=False)
        .sum()
        .sort_values("amount", ascending=False)
        .head(200)
    )
    st.dataframe(top)

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
    chart = alt.Chart(agg).mark_bar().encode(x="hour:O", y="amount:Q")
    st.altair_chart(chart, width='stretch')

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
    chart = alt.Chart(df).mark_line().encode(x="time:T", y="amount:Q")
    st.altair_chart(chart, width='stretch')

# -------------------------
# Panel de riesgo
# -------------------------
def show_risk(edges, root, chain="btc"):
    if not edges:
        st.info("Sin datos para panel de riesgo.")
        return

    unit = "ETH" if chain == "eth" else "BTC"
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
    col1.metric("Total entrante", f"{total_in:.8f} {unit}")
    col2.metric("Total saliente", f"{total_out:.8f} {unit}")
    col3.metric("Vecinos únicos", neighbors)

# -------------------------
# Dashboard principal
# -------------------------
def show_dashboard(addr, filters, chain="btc"):
    edges = fetch_subgraph(addr, depth=TRACER_PARAMS["max_hops"], chain=chain)

    edges = [e for e in edges if "amount" in e and e["amount"] is not None]

    if not edges:
        st.warning("No hay relaciones válidas para esta dirección.")
        return

    # Filtros
    edges = [e for e in edges if float(e["amount"]) >= filters["min_amount"]]
    if filters["only_hop1"]:
        edges = [e for e in edges if e.get("hop") == 1]
    if filters["only_fanin"]:
        edges = [e for e in edges if e.get("to_addr") == addr]
    if filters["only_fanout"]:
        edges = [e for e in edges if e.get("from_addr") == addr or (e.get("hop") is not None and int(e.get("hop")) > 1)]
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

    tabs = st.tabs(["Grafo", "Sankey", "Heatmap", "Timeline", "Tabla", "Riesgo", "Reporte IA", "Grafo Detallado"])

    with tabs[0]:
        show_graph(edges)

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
        # Convert labels to string for display
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
        # Select the columns to display: replace entity columns with label columns
        display_columns = ['from_addr', 'to_addr', 'amount', 'txid', 'hop', 'ts', 'is_change', 'from_label', 'to_label', 'time']
        # Ensure the columns exist in the dataframe
        display_columns = [col for col in display_columns if col in df.columns]
        st.dataframe(df[display_columns])

    with tabs[5]:
        show_risk(edges, addr, chain=chain)

    # -------------------------
    # REPORTE IA (V2 - Enhanced)
    # -------------------------
    with tabs[6]:
        st.subheader("Reporte IA (Ollama)")

        col_legacy, col_enhanced = st.columns(2)

        with col_legacy:
            if st.button("Generar reporte IA (simple)"):
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
                st.info(f"TXT: {paths.get('txt', '')}")
                st.info(f"MD: {paths.get('md', '')}")

        with col_enhanced:
            if st.button("Generar reporte IA + PDF (completo)"):
                with st.spinner("Generando reporte completo... esto puede tomar varios segundos."):
                    tracer = BTCForensicsPro(**TRACER_PARAMS, min_amount=filters["min_amount"])

                    # Use the new enhanced report generation
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

                        # Read the narrative from the metadata JSON (avoids calling Ollama again)
                        metadata_path = result.get("data_json", "")
                        if metadata_path and os.path.exists(metadata_path):
                            with open(metadata_path, "r", encoding="utf-8") as f:
                                meta = json.load(f)
                            st.session_state.ai_report = meta.get("ollama_narrative", "")
                        else:
                            st.session_state.ai_report = result.get("ollama_narrative", "")
                        st.session_state.transaction_graph = result.get("graph")

                    tracer.close()

        # Display current report
        if st.session_state.ai_report:
            st.markdown("### Reporte generado")
            st.write(st.session_state.ai_report)

        # Display enhanced report results
        if st.session_state.get("enhanced_report"):
            result = st.session_state.enhanced_report
            st.markdown("---")
            st.success("Reporte completo generado exitosamente!")

            folder = result.get("folder", "")
            pdf_path = result.get("pdf", "")
            html_path = result.get("html", "")

            if folder:
                st.info(f"Carpeta del analisis: **{folder}**")

                # Show folder contents as a table
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    if pdf_path and os.path.exists(pdf_path):
                        with open(pdf_path, "rb") as f:
                            st.download_button(
                                label="Descargar PDF",
                                data=f,
                                file_name=os.path.basename(pdf_path),
                                mime="application/pdf",
                            )
                    else:
                        pdf_error = result.get("pdf_error", "")
                        msg = "PDF no disponible"
                        if pdf_error:
                            msg += f": {pdf_error}"
                        else:
                            msg += " (verificar dependencias)"
                        st.warning(msg)

                with col_b:
                    if html_path and os.path.exists(html_path):
                        with open(html_path, "r", encoding="utf-8") as f:
                            st.download_button(
                                label="Descargar HTML",
                                data=f,
                                file_name=os.path.basename(html_path),
                                mime="text/html",
                            )

                with col_c:
                    csv_path = result.get("transactions_csv", "")
                    if csv_path and os.path.exists(csv_path):
                        with open(csv_path, "r", encoding="utf-8") as f:
                            st.download_button(
                                label="Descargar CSV",
                                data=f,
                                file_name=os.path.basename(csv_path),
                                mime="text/csv",
                            )

                # ZIP download with all files
                st.markdown("---")
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                    for fname in sorted(os.listdir(folder)):
                        fpath = os.path.join(folder, fname)
                        if os.path.isfile(fpath):
                            zf.write(fpath, arcname=fname)
                zip_buffer.seek(0)
                st.download_button(
                    label="Descargar todo (ZIP)",
                    data=zip_buffer,
                    file_name=f"reporte_{st.session_state.last_address[:12]}.zip",
                    mime="application/zip",
                    type="primary",
                )

                # List all files in folder
                st.markdown("**Archivos generados:**")
                if os.path.exists(folder):
                    for fname in sorted(os.listdir(folder)):
                        fpath = os.path.join(folder, fname)
                        size = os.path.getsize(fpath)
                        st.text(f"  {fname} ({size:,} bytes)")

    with tabs[7]:
        st.subheader("Grafo de Transacciones Detallado (PyVis)")
        if st.session_state.transaction_graph:
            st.components.v1.html(st.session_state.transaction_graph, height=750, scrolling=True)
        else:
            st.info("Presione 'Generar reporte IA + PDF' en la pestana 'Reporte IA' para construir y visualizar el grafo interactivo.")

# -------------------------
# MAIN UI
# -------------------------
def main():
    st.set_page_config(page_title="Dashboard Forense Multi-Chain", layout="wide")

    # Sidebar chain selector
    with st.sidebar:
        chain = st.selectbox("Blockchain", ["BTC", "ETH"], index=0)
        chain = chain.lower()
        unit = "ETH" if chain == "eth" else "BTC"
        TRACER_PARAMS["chain"] = chain

    st.title(f"Dashboard Forense {unit.upper()} — Filtros avanzados + Reporte IA")

    # Initialize session state variables
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


    addr_input = st.text_input(f"Dirección {unit.upper()}:", value=st.session_state.last_address or "")
    addr = addr_input.strip()

    st.markdown("### Filtros avanzados")

    col1, col2, col3 = st.columns(3)

    with col1:
        min_amount = st.number_input(f"Monto mínimo ({unit})", min_value=0.0, value=0.00001, step=0.00001, format="%.8f")
        only_hop1 = st.checkbox("Solo hop 1")
        hide_change = st.checkbox("Ocultar change outputs")

    with col2:
        only_fanin = st.checkbox("Solo FAN-IN")
        only_fanout = st.checkbox("Solo FAN-OUT")

    with col3:
        entity = st.selectbox("Filtrar por entidad", ["Todas", "exchange", "mixer", "bridge", "sanctioned", "other"])

    filters = {
        "min_amount": min_amount,
        "only_hop1": only_hop1,
        "hide_change": hide_change,
        "only_fanin": only_fanin,
        "only_fanout": only_fanout,
        "entity": entity,
        "_chain": chain,
    }

    if st.button("Procesar"):
        if not addr:
            st.error("Introduce una dirección válida.")
            return

        st.session_state.last_address = addr
        st.session_state.chain = chain
        st.session_state.ai_report = None

        tracer = BTCForensicsPro(**TRACER_PARAMS, min_amount=min_amount)
        if not address_has_relations(addr, chain=chain):
            ok = tracer.trace(addr)
            if not ok:
                detail = getattr(tracer, '_last_trace_error', '')
                msg = f"No se pudieron obtener transacciones para {addr} en {unit.upper()}."
                if detail:
                    msg += f"\n\nDetalle: {detail}"
                msg += "\n\nVerifica que la dirección sea válida y que ETHERSCAN_API_KEY esté configurada."
                st.error(msg)
                tracer.close()
                return
        tracer.close()
        st.session_state.analysis_done = True

    if st.session_state.analysis_done and st.session_state.last_address:
        show_dashboard(st.session_state.last_address, filters, chain=chain)

if __name__ == "__main__":
    main()
