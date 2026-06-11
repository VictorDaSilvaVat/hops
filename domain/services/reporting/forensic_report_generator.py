"""
Service for generating professional forensic reports.
"""
import json
import hashlib
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
import logging

from domain.ports.reporting import ReportGenerator, EvidenceTracker
from domain.models.address import Address, EntityType

logger = logging.getLogger(__name__)


class ForensicReportGenerator(ReportGenerator, EvidenceTracker):
    """Service for generating professional forensic reports with chain of custody."""

    def __init__(self, case_id: str = None, investigator: str = "HOPS System"):
        self.case_id = case_id or f"CASE_{int(time.time())}"
        self.investigator = investigator
        self.evidence_log: List[Dict[str, Any]] = []
        self.report_templates = self._load_report_templates()
        self.logger = logging.getLogger(__name__)

    def generate_report(self, analysis_data: Dict[str, Any], 
                       format_type: str = "json") -> str:
        """
        Generate a forensic report from analysis data.

        Args:
            analysis_data: Dictionary containing analysis results
            format_type: Output format ("json", "html", "txt")

        Returns:
            Report content as string
        """
        self.logger.info(f"Generating {format_type} report for case {self.case_id}")
        
        # Add metadata to analysis data
        report_data = self._prepare_report_data(analysis_data)
        
        if format_type.lower() == "json":
            return self._generate_json_report(report_data)
        elif format_type.lower() == "html":
            return self._generate_html_report(report_data)
        elif format_type.lower() == "txt":
            return self._generate_text_report(report_data)
        else:
            raise ValueError(f"Unsupported format type: {format_type}")

    def get_supported_formats(self) -> List[str]:
        """Get list of supported report formats."""
        return ["json", "html", "txt"]

    def record_evidence(self, evidence_id: str, description: str, 
                       source: str, timestamp: Optional[datetime] = None) -> str:
        """
        Record a piece of evidence with chain of custody information.

        Args:
            evidence_id: Unique identifier for the evidence
            description: Description of the evidence
            source: Source of the evidence (API call, file, etc.)
            timestamp: When the evidence was collected

        Returns:
            Evidence record ID
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        evidence_record = {
            "evidence_id": evidence_id,
            "description": description,
            "source": source,
            "timestamp": timestamp.isoformat(),
            "recorded_at": datetime.utcnow().isoformat(),
            "hash": self._generate_evidence_hash(evidence_id, description, source, timestamp)
        }
        
        self.evidence_log.append(evidence_record)
        self.logger.debug(f"Recorded evidence: {evidence_id}")
        
        return evidence_id

    def get_evidence_chain(self, evidence_id: str) -> List[Dict[str, Any]]:
        """
        Get the chain of custody for a piece of evidence.

        Args:
            evidence_id: Evidence identifier

        Returns:
            List of evidence handling records
        """
        return [ev for ev in self.evidence_log if ev["evidence_id"] == evidence_id]

    def _prepare_report_data(self, analysis_data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare data for report generation with metadata."""
        return {
            "case_information": {
                "case_id": self.case_id,
                "investigator": self.investigator,
                "generated_at": datetime.utcnow().isoformat(),
                "report_version": "1.0",
                "system": "HOPS Forensic Analysis System"
            },
            "analysis_results": analysis_data,
            "evidence_chain": self.evidence_log,
            "methodology": {
                "data_sources": ["Blockstream API", "WalletExplorer API"],
                "analysis_techniques": [
                    "Address clustering",
                    "Entity recognition",
                    "Transaction pattern analysis",
                    "Risk assessment"
                ],
                "limitations": [
                    "Analysis limited to available blockchain data",
                    "Entity recognition based on heuristics and known patterns",
                    "Real-time data subject to API availability and rate limits"
                ]
            }
        }

    def _generate_json_report(self, data: Dict[str, Any]) -> str:
        """Generate JSON format report."""
        return json.dumps(data, indent=2, default=str)

    def _generate_html_report(self, data: Dict[str, Any]) -> str:
        """Generate HTML format report."""
        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>HOPS Forensic Analysis Report - {case_id}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                .header {{ background-color: #f4f4f4; padding: 20px; border-radius: 5px; }}
                .section {{ margin: 20px 0; padding: 15px; border-left: 4px solid #007cba; }}
                .subsection {{ margin: 15px 0; padding: 10px; background-color: #f9f9f9; }}
                .metadata {{ font-size: 0.9em; color: #666; }}
                .evidence {{ background-color: #fff8dc; padding: 10px; margin: 10px 0; }}
                .warning {{ color: #d32f2f; }}
                .info {{ color: #1976d2; }}
                table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>HOPS Forensic Analysis Report</h1>
                <p><strong>Case ID:</strong> {case_id}</p>
                <p><strong>Investigator:</strong> {investigator}</p>
                <p><strong>Generated:</strong> {generated_at}</p>
            </div>
            
            <div class="section">
                <h2>Executive Summary</h2>
                <p>{executive_summary}</p>
            </div>
            
            <div class="section">
                <h2>Analysis Results</h2>
                {analysis_content}
            </div>
            
            <div class="section">
                <h2>Methodology</h2>
                <div class="subsection">
                    <h3>Data Sources</h3>
                    <ul>
                        {data_sources}
                    </ul>
                </div>
                <div class="subsection">
                    <h3>Analysis Techniques</h3>
                    <ul>
                        {analysis_techniques}
                    </ul>
                </div>
                <div class="subsection">
                    <h3>Limitations</h3>
                    <ul>
                        {limitations}
                    </ul>
                </div>
            </div>
            
            <div class="section">
                <h2>Evidence Chain of Custody</h2>
                {evidence_chain}
            </div>
            
            <div class="section">
                <h2>Report Metadata</h2>
                <p><strong>Report Version:</strong> {report_version}</p>
                <p><strong>System:</strong> {system}</p>
            </div>
        </body>
        </html>
        """
        
        # Extract data for template
        case_info = data.get("case_information", {})
        analysis_results = data.get("analysis_results", {})
        methodology = data.get("methodology", {})
        
        # Generate executive summary
        executive_summary = self._generate_executive_summary(analysis_results)
        
        # Generate analysis content
        analysis_content = self._generate_analysis_html(analysis_results)
        
        # Format lists for HTML
        data_sources = "".join([f"<li>{src}</li>" for src in methodology.get("data_sources", [])])
        analysis_techniques = "".join([f"<li>{tech}</li>" for tech in methodology.get("analysis_techniques", [])])
        limitations = "".join([f"<li>{lim}</li>" for lim in methodology.get("limitations", [])])
        
        # Generate evidence chain HTML
        evidence_chain = self._generate_evidence_chain_html(data.get("evidence_chain", []))
        
        return html_template.format(
            case_id=case_info.get("case_id", "Unknown"),
            investigator=case_info.get("investigator", "Unknown"),
            generated_at=case_info.get("generated_at", "Unknown"),
            report_version=case_info.get("report_version", "1.0"),
            system=case_info.get("system", "HOPS Forensic Analysis System"),
            executive_summary=executive_summary,
            analysis_content=analysis_content,
            data_sources=data_sources,
            analysis_techniques=analysis_techniques,
            limitations=limitations,
            evidence_chain=evidence_chain
        )

    def _generate_text_report(self, data: Dict[str, Any]) -> str:
        """Generate plain text format report."""
        case_info = data.get("case_information", {})
        analysis_results = data.get("analysis_results", {})
        methodology = data.get("methodology", {})
        evidence_chain = data.get("evidence_chain", [])
        
        report_lines = [
            "=" * 60,
            "HOPS FORENSIC ANALYSIS REPORT",
            "=" * 60,
            "",
            f"Case ID: {case_info.get('case_id', 'Unknown')}",
            f"Investigator: {case_info.get('investigator', 'Unknown')}",
            f"Generated: {case_info.get('generated_at', 'Unknown')}",
            f"Report Version: {case_info.get('report_version', '1.0')}",
            "",
            "EXECUTIVE SUMMARY",
            "-" * 40,
            self._generate_executive_summary(analysis_results),
            "",
            "ANALYSIS RESULTS",
            "-" * 40,
            self._generate_analysis_text(analysis_results),
            "",
            "METHODOLOGY",
            "-" * 40,
            "Data Sources:",
        ]
        
        for src in methodology.get("data_sources", []):
            report_lines.append(f"  • {src}")
        
        report_lines.extend([
            "",
            "Analysis Techniques:",
        ])
        
        for tech in methodology.get("analysis_techniques", []):
            report_lines.append(f"  • {tech}")
        
        report_lines.extend([
            "",
            "Limitations:",
        ])
        
        for lim in methodology.get("limitations", []):
            report_lines.append(f"  • {lim}")
        
        report_lines.extend([
            "",
            "EVIDENCE CHAIN OF CUSTODY",
            "-" * 40,
        ])
        
        if evidence_chain:
            for evidence in evidence_chain:
                report_lines.extend([
                    f"Evidence ID: {evidence.get('evidence_id', 'Unknown')}",
                    f"Description: {evidence.get('description', 'No description')}",
                    f"Source: {evidence.get('source', 'Unknown')}",
                    f"Timestamp: {evidence.get('timestamp', 'Unknown')}",
                    "-" * 20,
                ])
        else:
            report_lines.append("No evidence recorded.")
        
        report_lines.extend([
            "",
            "=" * 60,
            "END OF REPORT",
            "=" * 60
        ])
        
        return "\n".join(report_lines)

    def _generate_executive_summary(self, analysis_results: Dict[str, Any]) -> str:
        """Generate executive summary from analysis results."""
        # This would be customized based on the actual analysis results
        total_addresses = analysis_results.get("total_addresses_analyzed", 0)
        total_transactions = analysis_results.get("total_transactions_analyzed", 0)
        high_risk_entities = analysis_results.get("high_risk_entities_count", 0)
        
        summary = f"""
        This report analyzes {total_addresses} Bitcoin addresses and {total_transactions} 
        transactions. The analysis identified {high_risk_entities} high-risk entities 
        requiring further investigation. Key findings include transaction clustering 
        analysis, entity recognition results, and risk assessment scores.
        """.strip()
        
        return summary

    def _generate_analysis_html(self, analysis_results: Dict[str, Any]) -> str:
        """Generate HTML content for analysis results."""
        # This would be customized based on the actual analysis structure
        html = "<div class=\"subsection\">"
        html += "<h3>Address Analysis</h3>"
        html += f"<p>Total addresses analyzed: {analysis_results.get('total_addresses_analyzed', 0)}</p>"
        html += "</div>"
        
        html += "<div class=\"subsection\">"
        html += "<h3>Transaction Analysis</h3>"
        html += f"<p>Total transactions analyzed: {analysis_results.get('total_transactions_analyzed', 0)}</p>"
        html += "</div>"
        
        # Add clustering results if available
        if "clusters" in analysis_results:
            html += "<div class=\"subsection\">"
            html += "<h3>Transaction Clusters</h3>"
            html += f"<p>Number of clusters identified: {len(analysis_results.get('clusters', []))}</p>"
            html += "</div>"
        
        return html

    def _generate_analysis_text(self, analysis_results: Dict[str, Any]) -> str:
        """Generate text content for analysis results."""
        lines = [
            f"Total addresses analyzed: {analysis_results.get('total_addresses_analyzed', 0)}",
            f"Total transactions analyzed: {analysis_results.get('total_transactions_analyzed', 0)}",
        ]
        
        if "clusters" in analysis_results:
            lines.append(f"Number of clusters identified: {len(analysis_results.get('clusters', []))}")
        
        if "entity_distribution" in analysis_results:
            lines.append("")
            lines.append("Entity Distribution:")
            for entity_type, count in analysis_results.get("entity_distribution", {}).items():
                lines.append(f"  {entity_type}: {count}")
        
        return "\n".join(lines)

    def _generate_evidence_chain_html(self, evidence_log: List[Dict[str, Any]]) -> str:
        """Generate HTML for evidence chain of custody."""
        if not evidence_log:
            return "<p>No evidence recorded.</p>"
        
        html = "<table>"
        html += "<tr><th>Evidence ID</th><th>Description</th><th>Source</th><th>Timestamp</th></tr>"
        
        for evidence in evidence_log:
            html += "<tr>"
            html += f"<td>{evidence.get('evidence_id', 'N/A')}</td>"
            html += f"<td>{evidence.get('description', 'N/A')}</td>"
            html += f"<td>{evidence.get('source', 'N/A')}</td>"
            html += f"<td>{evidence.get('timestamp', 'N/A')}</td>"
            html += "</tr>"
        
        html += "</table>"
        return html

    def _generate_evidence_hash(self, evidence_id: str, description: str, 
                               source: str, timestamp: datetime) -> str:
        """Generate a hash for evidence integrity verification."""
        data = f"{evidence_id}{description}{source}{timestamp.isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()

    def _load_report_templates(self) -> Dict[str, str]:
        """Load report templates (placeholder for future expansion)."""
        return {
            "json": "json_template",
            "html": "html_template", 
            "txt": "text_template"
        }