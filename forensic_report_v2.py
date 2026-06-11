"""
Enhanced forensic report generator v2.
Produces comprehensive HTML and PDF reports with timeline, heatmap, graph and tables.
"""

import os
import json
import base64
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import networkx as nx
import pandas as pd

logger = logging.getLogger(__name__)

# Find the logo file (check multiple possible locations)
REPORT_LOGO_PATHS = [
    os.path.join(os.path.dirname(__file__), "reports", "logo.png"),
    os.path.join(os.path.dirname(__file__), "logo.png"),
    "reports/logo.png",
    "logo.png",
]
REPORT_LOGO = next((p for p in REPORT_LOGO_PATHS if os.path.exists(p)), None)
if REPORT_LOGO:
    logger.info(f"Report logo found: {REPORT_LOGO}")
else:
    logger.info("No report logo found (optional)")


class EnhancedForensicReporter:
    """Generates comprehensive forensic reports with visualizations in PDF format."""

    def __init__(self, output_dir: str = "reports"):
        self.output_dir = output_dir

    def generate_report_folder(
        self,
        address: str,
        edges: List[Dict[str, Any]],
        ollama_narrative: str,
        transaction_graph_html: str = "",
        filters: Optional[Dict] = None,
        sanctions: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate a complete report folder with HTML, PDF, charts, and raw data.

        Returns dict with paths to all generated files.
        """
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        folder = os.path.join(self.output_dir, address, timestamp)
        os.makedirs(folder, exist_ok=True)

        data = self._build_structured_data(address, edges, ollama_narrative, filters)
        if sanctions:
            data["sanctions"] = sanctions

        self._save_raw_data(folder, data, edges)

        chart_paths = self._generate_chart_images(folder, data, edges)

        graph_img_path = self._generate_graph_image(folder, edges, data)

        html_path = self._generate_html_report(folder, data, edges, chart_paths, graph_img_path)

        pdf_path = self._generate_pdf_report(html_path, folder)

        graph_path = None
        if transaction_graph_html:
            graph_path = os.path.join(folder, "transaction_graph.html")
            with open(graph_path, "w", encoding="utf-8") as f:
                f.write(transaction_graph_html)

        return {
            "folder": folder,
            "pdf": pdf_path,
            "html": html_path,
            "graph": graph_path,
            "data_json": os.path.join(folder, "analysis_metadata.json"),
            "transactions_csv": os.path.join(folder, "transactions.csv"),
            "timeline_chart": chart_paths.get("timeline"),
            "heatmap_chart": chart_paths.get("heatmap"),
            "graph_img": graph_img_path,
        }

    def _build_structured_data(self, address, edges, ollama_narrative, filters):
        """Build structured data dict from edges and narrative."""
        df = pd.DataFrame(edges) if edges else pd.DataFrame()

        timeline_data = []
        if not df.empty and "ts" in df.columns:
            df_time = df[df["ts"].notna()].copy()
            df_time["datetime"] = pd.to_datetime(df_time["ts"], unit="s")
            df_time = df_time.sort_values("datetime")
            for _, r in df_time.iterrows():
                timeline_data.append({
                    "datetime": r["datetime"].isoformat(),
                    "amount": float(r.get("amount", 0)),
                    "from": r.get("from_addr", ""),
                    "to": r.get("to_addr", ""),
                    "txid": r.get("txid", ""),
                })

        heatmap_data = {}
        if not df.empty and "ts" in df.columns:
            df_heat = df[df["ts"].notna()].copy()
            df_heat["hour"] = pd.to_datetime(df_heat["ts"], unit="s").dt.hour
            hourly = df_heat.groupby("hour").agg(
                total_amount=("amount", "sum"), tx_count=("txid", "count")
            ).to_dict("index")
            heatmap_data = {str(h): v for h, v in hourly.items()}

        entity_stats = {}
        if not df.empty:
            all_entities = []
            for col in ["from_entity", "to_entity"]:
                if col in df.columns:
                    all_entities.extend(df[col].dropna().tolist())
            for ent in set(all_entities):
                entity_stats[ent] = all_entities.count(ent)

        total_in = total_out = 0.0
        tx_count = 0
        if not df.empty:
            if "amount" in df.columns:
                df_amount = df[df["amount"].notna()]
                if "to_addr" in df_amount.columns:
                    total_in = df_amount[df_amount["to_addr"] == address]["amount"].sum()
                if "from_addr" in df_amount.columns:
                    total_out = df_amount[df_amount["from_addr"] == address]["amount"].sum()
                tx_count = len(df_amount)

        return {
            "address": address,
            "timestamp": datetime.utcnow().isoformat(),
            "total_transactions": tx_count,
            "total_in_btc": float(total_in),
            "total_out_btc": float(total_out),
            "unique_addresses": int(df["from_addr"].nunique() + df["to_addr"].nunique()) if not df.empty else 0,
            "entity_distribution": entity_stats,
            "timeline": timeline_data,
            "heatmap": heatmap_data,
            "ollama_narrative": ollama_narrative,
            "filters": filters or {},
        }

    def _save_raw_data(self, folder, data, edges):
        """Save all raw data files (JSON, CSV)."""
        with open(os.path.join(folder, "analysis_metadata.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str, ensure_ascii=False)

        if edges:
            df = pd.DataFrame(edges)
            for col in ["from_labels", "to_labels"]:
                if col in df.columns:
                    df[col] = df[col].apply(
                        lambda x: ", ".join(x) if isinstance(x, list) else str(x) if x else ""
                    )
            df.to_csv(os.path.join(folder, "transactions.csv"), index=False, encoding="utf-8")

        with open(os.path.join(folder, "timeline_data.json"), "w", encoding="utf-8") as f:
            json.dump(data.get("timeline", []), f, indent=2, default=str)

        with open(os.path.join(folder, "heatmap_data.json"), "w", encoding="utf-8") as f:
            json.dump(data.get("heatmap", {}), f, indent=2, default=str)

        sankey_data = []
        if edges:
            df = pd.DataFrame(edges)
            if "amount" in df.columns:
                sankey_df = df.groupby(["from_addr", "to_addr"], as_index=False)["amount"].sum()
                sankey_data = sankey_df.to_dict("records")
        with open(os.path.join(folder, "sankey_data.json"), "w", encoding="utf-8") as f:
            json.dump(sankey_data, f, indent=2, default=str)

        logger.info(f"Raw data saved to {folder}")

    def _generate_chart_images(self, folder, data, edges):
        """Generate timeline and heatmap charts as PNG images."""
        paths = {}
        df = pd.DataFrame(edges) if edges else pd.DataFrame()
        if df.empty:
            return paths

        if "ts" in df.columns:
            try:
                fig, ax = plt.subplots(figsize=(12, 4))
                df_time = df[df["ts"].notna()].copy()
                df_time["datetime"] = pd.to_datetime(df_time["ts"], unit="s")
                df_time = df_time.sort_values("datetime")
                df_time["amount_btc"] = df_time["amount"].astype(float)

                ax.plot(df_time["datetime"], df_time["amount_btc"],
                        color="#2196F3", linewidth=1, alpha=0.8, marker="o", markersize=3)
                ax.fill_between(df_time["datetime"], df_time["amount_btc"], alpha=0.1, color="#2196F3")
                ax.set_xlabel("Fecha / Hora (UTC)")
                ax.set_ylabel("Monto (BTC)")
                ax.set_title("Linea de Tiempo de Transacciones", fontsize=13, fontweight="bold")
                ax.grid(True, alpha=0.3)
                ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d %H:%M"))
                plt.xticks(rotation=45)
                plt.tight_layout()

                timeline_path = os.path.join(folder, "timeline_chart.png")
                plt.savefig(timeline_path, dpi=150, bbox_inches="tight")
                plt.close(fig)
                paths["timeline"] = timeline_path
            except Exception as e:
                logger.error(f"Error generating timeline chart: {e}")

        if "ts" in df.columns:
            try:
                df_heat = df[df["ts"].notna()].copy()
                df_heat["hour"] = pd.to_datetime(df_heat["ts"], unit="s").dt.hour
                hourly = df_heat.groupby("hour").agg(
                    total_amount=("amount", "sum"), tx_count=("txid", "count")
                ).reset_index()

                fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))

                ax1.bar(hourly["hour"], hourly["total_amount"], color="#FF9800", alpha=0.8, width=0.7)
                ax1.set_xlabel("Hora del dia (UTC)")
                ax1.set_ylabel("Monto total (BTC)")
                ax1.set_title("Distribucion por Hora - Monto", fontsize=11, fontweight="bold")
                ax1.set_xticks(range(24))
                ax1.grid(True, alpha=0.3, axis="y")

                ax2.bar(hourly["hour"], hourly["tx_count"], color="#4CAF50", alpha=0.8, width=0.7)
                ax2.set_xlabel("Hora del dia (UTC)")
                ax2.set_ylabel("Cantidad de TX")
                ax2.set_title("Distribucion por Hora - Transacciones", fontsize=11, fontweight="bold")
                ax2.set_xticks(range(24))
                ax2.grid(True, alpha=0.3, axis="y")

                plt.tight_layout()
                heatmap_path = os.path.join(folder, "heatmap_chart.png")
                plt.savefig(heatmap_path, dpi=150, bbox_inches="tight")
                plt.close(fig)
                paths["heatmap"] = heatmap_path
            except Exception as e:
                logger.error(f"Error generating heatmap chart: {e}")

        return paths

    def _generate_graph_image(self, folder, edges, data):
        """Generate a static graph visualization as PNG using networkx + matplotlib."""
        graph_path = os.path.join(folder, "graph_chart.png")
        df = pd.DataFrame(edges) if edges else pd.DataFrame()
        if df.empty:
            return None
        try:
            G = nx.DiGraph()
            for _, r in df.iterrows():
                frm = r.get("from_addr", "")
                to = r.get("to_addr", "")
                if frm and to:
                    amt = float(r.get("amount", 0))
                    G.add_edge(frm, to, weight=amt, txid=r.get("txid", ""))

            if G.number_of_nodes() == 0:
                return None

            fig, ax = plt.subplots(figsize=(12, 10))
            pos = nx.spring_layout(G, k=2.5, iterations=50, seed=42)

            edge_weights = [max(0.5, G[u][v].get("weight", 1)) for u, v in G.edges()]
            max_w = max(edge_weights) if edge_weights else 1
            edge_widths = [1 + 4 * (w / max_w) for w in edge_weights]

            node_colors = []
            address = data.get("address", "")
            for node in G.nodes():
                if node == address:
                    node_colors.append("#e53935")
                elif node in df["from_addr"].values and G.out_degree(node) > G.in_degree(node):
                    node_colors.append("#43a047")
                else:
                    node_colors.append("#1e88e5")

            node_sizes = []
            for node in G.nodes():
                if node == address:
                    node_sizes.append(500)
                else:
                    deg = G.degree(node)
                    node_sizes.append(100 + deg * 30)

            nx.draw_networkx_edges(G, pos, alpha=0.3, width=edge_widths, arrows=True,
                                   arrowstyle="->", arrowsize=12, ax=ax)
            nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=node_sizes,
                                   alpha=0.9, ax=ax)

            labels = {n: n[:8] + "..." for n in G.nodes()}
            nx.draw_networkx_labels(G, pos, labels, font_size=6, font_color="#333", ax=ax)

            ax.set_title("Grafo de Transacciones", fontsize=14, fontweight="bold", pad=15)
            ax.axis("off")

            legend_elements = [
                plt.Rectangle((0, 0), 1, 1, color="#e53935", label="Direccion analizada"),
                plt.Rectangle((0, 0), 1, 1, color="#43a047", label="Remitente"),
                plt.Rectangle((0, 0), 1, 1, color="#1e88e5", label="Destinatario"),
            ]
            ax.legend(handles=legend_elements, loc="upper right", fontsize=8)

            plt.tight_layout()
            plt.savefig(graph_path, dpi=150, bbox_inches="tight")
            plt.close(fig)
            logger.info(f"Graph image saved to {graph_path}")
            return graph_path
        except Exception as e:
            logger.error(f"Error generating graph image: {e}")
            return None

    def _generate_html_report(self, folder, data, edges, chart_paths, graph_img_path=None):
        """Generate a comprehensive HTML report."""
        # Read logo as base64
        logo_b64 = ""
        if REPORT_LOGO and os.path.exists(REPORT_LOGO):
            with open(REPORT_LOGO, "rb") as f:
                logo_b64 = base64.b64encode(f.read()).decode("utf-8")

        # Read chart images as base64
        timeline_img_b64 = ""
        if chart_paths.get("timeline") and os.path.exists(chart_paths["timeline"]):
            with open(chart_paths["timeline"], "rb") as f:
                timeline_img_b64 = base64.b64encode(f.read()).decode("utf-8")

        heatmap_img_b64 = ""
        if chart_paths.get("heatmap") and os.path.exists(chart_paths["heatmap"]):
            with open(chart_paths["heatmap"], "rb") as f:
                heatmap_img_b64 = base64.b64encode(f.read()).decode("utf-8")

        graph_img_b64 = ""
        if graph_img_path and os.path.exists(graph_img_path):
            with open(graph_img_path, "rb") as f:
                graph_img_b64 = base64.b64encode(f.read()).decode("utf-8")

        tx_rows_html = ""
        if edges:
            for e in edges[:200]:
                from_addr = e.get("from_addr", "")
                to_addr = e.get("to_addr", "")
                amount = float(e.get("amount", 0))
                txid = e.get("txid", "")[:16] + "..."
                hop = e.get("hop", "")
                from_entity = e.get("from_entity", "")
                to_entity = e.get("to_entity", "")

                from_labels = e.get("from_labels", "")
                to_labels = e.get("to_labels", "")
                if isinstance(from_labels, list):
                    from_labels = ", ".join(from_labels)
                if isinstance(to_labels, list):
                    to_labels = ", ".join(to_labels)

                ts = e.get("ts")
                dt_str = datetime.utcfromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S") if ts else ""

                tx_rows_html += f"""<tr>
                    <td title="{from_addr}">{from_addr[:20]}...</td>
                    <td title="{to_addr}">{to_addr[:20]}...</td>
                    <td class="num">{amount:.8f}</td>
                    <td class="num">{dt_str}</td>
                    <td>{from_entity}</td>
                    <td>{to_entity}</td>
                    <td>{from_labels}</td>
                    <td>{to_labels}</td>
                    <td class="num">{hop}</td>
                </tr>"""

        sankey_rows_html = ""
        if edges:
            df_sankey = pd.DataFrame(edges)
            if "amount" in df_sankey.columns:
                sankey_df = df_sankey.groupby(["from_addr", "to_addr"], as_index=False)["amount"].sum()
                sankey_df = sankey_df.sort_values("amount", ascending=False).head(50)
                for _, r in sankey_df.iterrows():
                    sankey_rows_html += f"""<tr>
                        <td>{r["from_addr"][:20]}...</td>
                        <td>{r["to_addr"][:20]}...</td>
                        <td class="num">{float(r["amount"]):.8f}</td>
                    </tr>"""

        entity_rows_html = ""
        for ent, count in sorted(data.get("entity_distribution", {}).items(), key=lambda x: -x[1]):
            entity_rows_html += f"<tr><td>{ent}</td><td class='num'>{count}</td></tr>"

        sanctions = data.get("sanctions", {})
        san_flag = sanctions.get("sanctioned")
        san_matches = sanctions.get("matches", [])
        if san_flag is True:
            san_badge = '<span class="sanctioned-badge">SANCIONADO</span>'
            san_text = "Esta direccion APARECE en listas de sanciones."
        elif san_flag is False:
            san_badge = '<span class="clean-badge">SIN SANCIONES</span>'
            san_text = "Esta direccion NO aparece en listas de sanciones conocidas."
        else:
            san_badge = '<span class="unknown-badge">NO VERIFICADO</span>'
            san_text = "No se pudo verificar contra listas de sanciones."

        san_matches_html = ""
        if san_matches:
            san_matches_html = "<h4>Coincidencias encontradas:</h4><ul>"
            for m in san_matches:
                san_matches_html += f"<li>{m}</li>"
            san_matches_html += "</ul>"

        ollama_narrative = data.get("ollama_narrative", "")

        html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Reporte Forense BTC - {data["address"][:20]}</title>
<style>
    @page {{ size: A4; margin: 2cm; }}
    * {{ box-sizing: border-box; }}
    body {{ font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif; font-size: 10pt; line-height: 1.5; color: #222; }}
    .cover {{ text-align: center; padding: 60px 0; page-break-after: always; }}
    .cover h1 {{ font-size: 26pt; color: #0d47a1; margin-bottom: 10px; }}
    .cover .subtitle {{ font-size: 14pt; color: #555; }}
    .cover .meta {{ margin-top: 40px; font-size: 10pt; color: #888; }}
    h2 {{ color: #0d47a1; border-bottom: 2px solid #0d47a1; padding-bottom: 5px; margin-top: 30px; }}
    h3 {{ color: #1565c0; margin-top: 20px; }}
    table {{ width: 100%; border-collapse: collapse; margin: 15px 0; font-size: 8pt; }}
    th, td {{ border: 1px solid #ddd; padding: 6px 8px; text-align: left; }}
    th {{ background-color: #0d47a1; color: white; font-weight: 600; }}
    tr:nth-child(even) {{ background-color: #f5f5f5; }}
    .num {{ text-align: right; font-family: 'Consolas', monospace; }}
    .chart-container {{ text-align: center; margin: 20px 0; }}
    .chart-container img {{ max-width: 100%; height: auto; }}
    .narrative {{ background: #f5f5f5; padding: 15px; border-left: 4px solid #0d47a1; margin: 15px 0; white-space: pre-wrap; word-break: break-word; }}
    .summary-cards {{ display: flex; gap: 10px; margin: 15px 0; }}
    .summary-card {{ flex: 1; background: #f5f5f5; padding: 15px; text-align: center; border-radius: 4px; }}
    .summary-card .value {{ font-size: 18pt; font-weight: bold; color: #0d47a1; }}
    .summary-card .label {{ font-size: 8pt; color: #666; }}
    .section-break {{ page-break-before: always; }}
    .footer {{ text-align: center; color: #999; font-size: 7pt; margin-top: 30px; border-top: 1px solid #ddd; padding-top: 10px; }}
    .sanctioned-badge {{ display: inline-block; background: #d32f2f; color: white; padding: 4px 12px; border-radius: 4px; font-weight: bold; font-size: 11pt; }}
    .clean-badge {{ display: inline-block; background: #388e3c; color: white; padding: 4px 12px; border-radius: 4px; font-weight: bold; font-size: 11pt; }}
    .unknown-badge {{ display: inline-block; background: #888; color: white; padding: 4px 12px; border-radius: 4px; font-weight: bold; font-size: 11pt; }}
</style>
</head>
<body>

<div class="cover">
    <div class="logo">{"<img src='data:image/png;base64," + logo_b64 + "' alt='Logo' style='max-width:300px;'>" if logo_b64 else ""}</div>
    <h1>Reporte Forense de Bitcoin</h1>
    <div class="subtitle">Analisis de Transacciones y Entidades</div>
    <div class="meta">
        <p><strong>Direccion:</strong> {data["address"]}</p>
        <p><strong>Fecha:</strong> {data["timestamp"]}</p>
        <p><strong>Total Transacciones:</strong> {data["total_transactions"]}</p>
        <p><strong>Total Recibido:</strong> {data["total_in_btc"]:.8f} BTC</p>
        <p><strong>Total Enviado:</strong> {data["total_out_btc"]:.8f} BTC</p>
    </div>
</div>

<h2>1. Resumen Ejecutivo</h2>
<div class="summary-cards">
    <div class="summary-card">
        <div class="value">{data["total_transactions"]}</div>
        <div class="label">Transacciones</div>
    </div>
    <div class="summary-card">
        <div class="value">{data["total_in_btc"]:.4f}</div>
        <div class="label">BTC Recibido</div>
    </div>
    <div class="summary-card">
        <div class="value">{data["total_out_btc"]:.4f}</div>
        <div class="label">BTC Enviado</div>
    </div>
    <div class="summary-card">
        <div class="value">{data["unique_addresses"]}</div>
        <div class="label">Direcciones Unicas</div>
    </div>
</div>

<h2>2. Verificacion de Sanciones</h2>
<p>{san_badge} &nbsp; {san_text}</p>
{san_matches_html}

<h2>3. Analisis Forense IA</h2>
<div class="narrative">{ollama_narrative}</div>

<h2>4. Distribucion de Entidades</h2>
<table>
<tr><th>Entidad</th><th class="num">Cantidad</th></tr>
{entity_rows_html}
</table>

<div class="section-break"></div>
<h2>5. Linea de Tiempo</h2>
<p>Evolucion temporal de las transacciones asociadas a la direccion analizada.</p>
<div class="chart-container">
    <img src="data:image/png;base64,{timeline_img_b64}" alt="Timeline Chart">
</div>

<h2>6. Distribucion Horaria (Heatmap)</h2>
<p>Distribucion de montos y cantidad de transacciones por hora del dia (UTC).</p>
<div class="chart-container">
    <img src="data:image/png;base64,{heatmap_img_b64}" alt="Heatmap Chart">
</div>

<h2>7. Grafo de Transacciones</h2>
<p>Representacion visual de las conexiones entre direcciones. El nodo rojo es la direccion analizada.</p>
<div class="chart-container">
    <img src="data:image/png;base64,{graph_img_b64}" alt="Transaction Graph">
</div>

<div class="section-break"></div>
<h2>8. Flujo de Fondos (Sankey - Top 50)</h2>
<p>Principales flujos de fondos entre direcciones agrupados por par origen-destino.</p>
<table>
<tr><th>Origen</th><th>Destino</th><th class="num">Monto (BTC)</th></tr>
{sankey_rows_html}
</table>

<div class="section-break"></div>
<h2>9. Tabla de Transacciones</h2>
<p>Listado detallado de transacciones (maximo 200).</p>
<table>
<tr>
    <th>Desde</th><th>Hacia</th><th class="num">Monto (BTC)</th>
    <th class="num">Fecha</th><th>Ent. Origen</th><th>Ent. Destino</th>
    <th>Labels Origen</th><th>Labels Destino</th><th>Hop</th>
</tr>
{tx_rows_html}
</table>

<div class="footer">
    <p>Generado por HOPS - Sistema de Analisis Forense Bitcoin | {data["timestamp"]}</p>
</div>

</body>
</html>"""

        html_path = os.path.join(folder, "report.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)

        logger.info(f"HTML report saved to {html_path}")
        return html_path

    def _generate_pdf_report(self, html_path, folder):
        """Generate PDF report using fpdf2."""
        import os, json
        pdf_path = os.path.join(folder, "report.pdf")
        try:
            from fpdf import FPDF

            # Read the HTML to extract data (we already have the metadata JSON)
            meta_path = os.path.join(folder, "analysis_metadata.json")
            data = {}
            if os.path.exists(meta_path):
                with open(meta_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

            # Determine chart paths
            timeline_png = os.path.join(folder, "timeline_chart.png")
            heatmap_png = os.path.join(folder, "heatmap_chart.png")
            graph_png = os.path.join(folder, "graph_chart.png")

            class PDF(FPDF):
                def header(self):
                    self.set_font("Helvetica", "B", 9)
                    self.set_text_color(100, 100, 100)
                    self.cell(0, 6, "HOPS - Reporte Forense Bitcoin", align="R", new_x="LMARGIN", new_y="NEXT")
                    self.line(10, self.get_y(), 200, self.get_y())
                    self.ln(3)

                def footer(self):
                    self.set_y(-15)
                    self.set_font("Helvetica", "I", 7)
                    self.set_text_color(150, 150, 150)
                    self.cell(0, 10, f"Pagina {self.page_no()}/{{nb}}", align="C")

                def section_title(self, title):
                    self.set_font("Helvetica", "B", 14)
                    self.set_text_color(13, 71, 161)
                    self.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
                    self.set_draw_color(13, 71, 161)
                    self.line(10, self.get_y(), 200, self.get_y())
                    self.ln(4)

                def body_text(self, text):
                    self.set_font("Helvetica", "", 9)
                    self.set_text_color(34, 34, 34)
                    self.multi_cell(0, 5, text)
                    self.ln(3)

            pdf = PDF()
            pdf.alias_nb_pages()

            # --- Cover Page ---
            pdf.add_page()
            # Logo
            logo_path = REPORT_LOGO
            if logo_path and os.path.exists(logo_path):
                pdf.image(logo_path, x=55, w=100)
                pdf.ln(15)
            else:
                pdf.ln(30)
            pdf.set_font("Helvetica", "B", 24)
            pdf.set_text_color(13, 71, 161)
            pdf.cell(0, 15, "Reporte Forense de Bitcoin", align="C", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(5)
            pdf.set_font("Helvetica", "", 13)
            pdf.set_text_color(85, 85, 85)
            pdf.cell(0, 8, "Analisis de Transacciones y Entidades", align="C", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(15)
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(100, 100, 100)
            addr = data.get("address", "")
            pdf.cell(0, 7, f"Direccion: {addr}", align="C", new_x="LMARGIN", new_y="NEXT")
            pdf.cell(0, 7, f"Fecha: {data.get('timestamp', '')}", align="C", new_x="LMARGIN", new_y="NEXT")
            pdf.cell(0, 7, f"Total Transacciones: {data.get('total_transactions', 0)}", align="C", new_x="LMARGIN", new_y="NEXT")
            pdf.cell(0, 7, f"Total Recibido: {data.get('total_in_btc', 0):.8f} BTC", align="C", new_x="LMARGIN", new_y="NEXT")
            pdf.cell(0, 7, f"Total Enviado: {data.get('total_out_btc', 0):.8f} BTC", align="C", new_x="LMARGIN", new_y="NEXT")

            # --- Executive Summary ---
            pdf.add_page()
            pdf.section_title("1. Resumen Ejecutivo")
            pdf.body_text(
                f"Este reporte analiza {data.get('total_transactions', 0)} transacciones "
                f"asociadas a la direccion {addr}. "
                f"Se identificaron {data.get('unique_addresses', 0)} direcciones unicas "
                f"con un volumen total de {data.get('total_in_btc', 0):.4f} BTC recibidos "
                f"y {data.get('total_out_btc', 0):.4f} BTC enviados."
            )

            # --- Sanctions Check ---
            sanctions = data.get("sanctions", {})
            san_flag = sanctions.get("sanctioned")
            pdf.section_title("2. Verificacion de Sanciones")
            if san_flag is True:
                pdf.set_font("Helvetica", "B", 11)
                pdf.set_text_color(211, 47, 47)
                pdf.cell(0, 8, "SANCIONADO - La direccion aparece en listas de sanciones.", new_x="LMARGIN", new_y="NEXT")
            elif san_flag is False:
                pdf.set_font("Helvetica", "B", 11)
                pdf.set_text_color(56, 142, 60)
                pdf.cell(0, 8, "SIN SANCIONES - No aparece en listas de sanciones conocidas.", new_x="LMARGIN", new_y="NEXT")
            else:
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(100, 100, 100)
                pdf.cell(0, 8, "No se pudo verificar contra listas de sanciones.", new_x="LMARGIN", new_y="NEXT")
            san_matches = sanctions.get("matches", [])
            if san_matches:
                pdf.set_font("Helvetica", "B", 9)
                pdf.set_text_color(34, 34, 34)
                pdf.cell(0, 7, "Coincidencias:", new_x="LMARGIN", new_y="NEXT")
                pdf.set_font("Helvetica", "", 8)
                for m in san_matches:
                    pdf.cell(0, 5, f"  - {m}", new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(34, 34, 34)

            # --- Ollama Narrative ---
            narrative = data.get("ollama_narrative", "")
            if narrative:
                pdf.section_title("3. Analisis Forense IA")
                for para in narrative.split("\n\n"):
                    para = para.strip()
                    if para:
                        pdf.body_text(para)

            # --- Entity Distribution ---
            ed = data.get("entity_distribution", {})
            if ed:
                pdf.section_title("4. Distribucion de Entidades")
                pdf.set_font("Helvetica", "B", 9)
                pdf.set_fill_color(13, 71, 161)
                pdf.set_text_color(255, 255, 255)
                pdf.cell(80, 7, "Entidad", border=1, fill=True, align="C")
                pdf.cell(30, 7, "Cantidad", border=1, fill=True, align="C", new_x="LMARGIN", new_y="NEXT")
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(34, 34, 34)
                for ent, count in sorted(ed.items(), key=lambda x: -x[1]):
                    pdf.cell(80, 6, str(ent), border=1)
                    pdf.cell(30, 6, str(count), border=1, align="C", new_x="LMARGIN", new_y="NEXT")

            # --- Timeline Chart ---
            if os.path.exists(timeline_png):
                pdf.add_page()
                pdf.section_title("5. Linea de Tiempo")
                pdf.body_text("Evolucion temporal de las transacciones asociadas.")
                pdf.image(timeline_png, x=10, w=190)

            # --- Heatmap Chart ---
            if os.path.exists(heatmap_png):
                pdf.section_title("6. Distribucion Horaria (Heatmap)")
                pdf.body_text("Distribucion de montos y transacciones por hora del dia (UTC).")
                pdf.image(heatmap_png, x=10, w=190)

            # --- Graph Image ---
            pdf.add_page()
            pdf.section_title("7. Grafo de Transacciones")
            pdf.body_text(
                "Representacion visual de las conexiones entre direcciones. "
                "El nodo rojo es la direccion analizada, los verdes son remitentes y los azules destinatarios."
            )
            if os.path.exists(graph_png):
                pdf.image(graph_png, x=10, w=190)

            # --- Transaction Table ---
            csv_path = os.path.join(folder, "transactions.csv")
            if os.path.exists(csv_path):
                pdf.add_page()
                pdf.section_title("8. Tabla de Transacciones")
                import csv as csv_mod
                with open(csv_path, "r", encoding="utf-8") as f:
                    reader = csv_mod.reader(f)
                    rows_list = list(reader)

                if len(rows_list) > 1:
                    # Limit to first 50 rows for PDF
                    display_rows = rows_list[:51]
                    headers = display_rows[0]
                    data_rows = display_rows[1:]

                    pdf.set_font("Helvetica", "B", 6)
                    pdf.set_fill_color(13, 71, 161)
                    pdf.set_text_color(255, 255, 255)

                    # Truncate headers
                    col_widths = [30, 30, 20, 30, 15, 15, 20, 20, 8]
                    h_labels = [h[:12] for h in headers[:9]]
                    for i, h in enumerate(h_labels[:9]):
                        pdf.cell(col_widths[i], 6, h, border=1, fill=True, align="C")
                    pdf.ln()

                    pdf.set_font("Helvetica", "", 5)
                    pdf.set_text_color(34, 34, 34)
                    fill = False
                    for row in data_rows:
                        if pdf.get_y() > 270:
                            pdf.add_page()
                            pdf.set_font("Helvetica", "B", 6)
                            pdf.set_fill_color(13, 71, 161)
                            pdf.set_text_color(255, 255, 255)
                            for i, h in enumerate(h_labels[:9]):
                                pdf.cell(col_widths[i], 6, h, border=1, fill=True, align="C")
                            pdf.ln()
                            pdf.set_font("Helvetica", "", 5)
                            pdf.set_text_color(34, 34, 34)
                        for i in range(min(9, len(row))):
                            txt = str(row[i])[:min(16, col_widths[i] // 2)]
                            pdf.cell(col_widths[i], 5, txt, border=1, fill=fill)
                        pdf.ln()
                        fill = not fill

            pdf.output(pdf_path)
            logger.info(f"PDF report saved to {pdf_path}")
            return pdf_path

        except ImportError as e:
            logger.warning(f"fpdf2 not available ({e}), PDF generation skipped")
            return None
        except Exception as e:
            logger.error(f"Error generating PDF: {e}")
            return None
