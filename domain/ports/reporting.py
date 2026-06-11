"""
Ports (interfaces) for reporting functionality.
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
import datetime as dt


class ReportGenerator(ABC):
    """Abstract interface for report generation."""

    @abstractmethod
    def generate_report(self, analysis_data: Dict[str, Any], 
                       format_type: str = "json") -> str:
        """
        Generate a report from analysis data.

        Args:
            analysis_data: Dictionary containing analysis results
            format_type: Output format ("json", "html", "txt")

        Returns:
            Report content as string
        """
        pass

    @abstractmethod
    def get_supported_formats(self) -> List[str]:
        """
        Get list of supported report formats.

        Returns:
            List of supported format strings
        """
        pass


class EvidenceTracker(ABC):
    """Abstract interface for evidence tracking and chain of custody."""

    @abstractmethod
    def record_evidence(self, evidence_id: str, description: str, 
                       source: str, timestamp: Optional[dt.datetime] = None) -> str:
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
        pass

    @abstractmethod
    def get_evidence_chain(self, evidence_id: str) -> List[Dict[str, Any]]:
        """
        Get the chain of custody for a piece of evidence.

        Args:
            evidence_id: Evidence identifier

        Returns:
            List of evidence handling records
        """
        pass