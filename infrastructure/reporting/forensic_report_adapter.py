"""
Adapter for forensic reporting functionality.
"""
import logging
import datetime
from typing import Optional

from domain.services.reporting.forensic_report_generator import ForensicReportGenerator
from domain.ports.reporting import ReportGenerator, EvidenceTracker

logger = logging.getLogger(__name__)


class ForensicReportAdapter(ReportGenerator, EvidenceTracker):
    """Adapter that makes ForensicReportGenerator conform to reporting ports."""

    def __init__(self, case_id: str = None, investigator: str = "HOPS System"):
        self.generator = ForensicReportGenerator(case_id=case_id, investigator=investigator)
        self.logger = logger

    def generate_report(self, analysis_data: dict, format_type: str = "json") -> str:
        """
        Generate a report from analysis data.

        Args:
            analysis_data: Dictionary containing analysis results
            format_type: Output format ("json", "html", "txt")

        Returns:
            Report content as string
        """
        try:
            return self.generator.generate_report(analysis_data, format_type)
        except Exception as e:
            self.logger.error(f"Error generating report: {e}")
            # Return a basic error report
            error_data = {
                "error": "Report generation failed",
                "details": str(e),
                "timestamp": datetime.datetime.utcnow().isoformat()
            }
            return __import__('json').dumps(error_data, indent=2)

    def get_supported_formats(self) -> list:
        """Get list of supported report formats."""
        return self.generator.get_supported_formats()

    def record_evidence(self, evidence_id: str, description: str, 
                       source: str, timestamp: Optional[datetime.datetime] = None) -> str:
        """
        Record a piece of evidence with chain of custody information.

        Args:
            evidence_id: Unique identifier for the evidence
            description: Description of the evidence
            source: Source of the evidence
            timestamp: When the evidence was collected

        Returns:
            Evidence record ID
        """
        return self.generator.record_evidence(evidence_id, description, source, timestamp)

    def get_evidence_chain(self, evidence_id: str) -> list:
        """
        Get the chain of custody for a piece of evidence.

        Args:
            evidence_id: Evidence identifier

        Returns:
            List of evidence handling records
        """
        return self.generator.get_evidence_chain(evidence_id)