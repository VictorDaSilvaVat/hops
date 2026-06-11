"""
Configuration management for the HOPS forensic system.
"""
import os
from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum


class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class Neo4jConfig:
    """Neo4j database configuration."""
    uri: str = field(default_factory=lambda: os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    user: str = field(default_factory=lambda: os.getenv("NEO4J_USER", "neo4j"))
    password: str = field(default_factory=lambda: os.getenv("NEO4J_PASSWORD", "neo4jneo4j"))
    
    def validate(self) -> List[str]:
        """Validate Neo4j configuration."""
        errors = []
        if not self.uri:
            errors.append("NEO4J_URI is required")
        if not self.user:
            errors.append("NEO4J_USER is required")
        if not self.password:
            errors.append("NEO4J_PASSWORD is required")
        return errors


@dataclass
class APIConfig:
    """External API configuration."""
    blockstream_base_url: str = field(
        default_factory=lambda: os.getenv("BLOCKSTREAM_BASE_URL", "https://blockstream.info/api")
    )
    walletexplorer_base_url: str = field(
        default_factory=lambda: os.getenv("WALLETEXPLORER_BASE_URL", "https://www.walletexplorer.com/api/1/")
    )
    ollama_base_url: str = field(
        default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    )
    ollama_model: str = field(
        default_factory=lambda: os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct-q4_K_M")
    )
    
    # Rate limiting and retry
    timeout: int = field(default_factory=lambda: int(os.getenv("API_TIMEOUT", "10")))
    retries: int = field(default_factory=lambda: int(os.getenv("API_RETRIES", "3")))
    retry_delay: float = field(default_factory=lambda: float(os.getenv("API_RETRY_DELAY", "0.5")))
    rate_limit_delay: float = field(default_factory=lambda: float(os.getenv("API_RATE_LIMIT_DELAY", "0.1")))
    
    # Sanctions API
    sanctions_internal_key: str = field(
        default_factory=lambda: os.getenv("SANCTIONS_INTERNAL_KEY", "")
    )
    
    # Caching
    cache_ttl_seconds: int = field(
        default_factory=lambda: int(os.getenv("CACHE_TTL_SECONDS", "300"))  # 5 minutes
    )
    max_cache_size: int = field(
        default_factory=lambda: int(os.getenv("MAX_CACHE_SIZE", "1000"))
    )
    
    def validate(self) -> List[str]:
        """Validate API configuration."""
        errors = []
        if self.timeout <= 0:
            errors.append("API_TIMEOUT must be positive")
        if self.retries < 0:
            errors.append("API_RETRIES must be non-negative")
        if self.retry_delay < 0:
            errors.append("API_RETRY_DELAY must be non-negative")
        if self.rate_limit_delay < 0:
            errors.append("API_RATE_LIMIT_DELAY must be non-negative")
        if self.cache_ttl_seconds <= 0:
            errors.append("CACHE_TTL_SECONDS must be positive")
        if self.max_cache_size <= 0:
            errors.append("MAX_CACHE_SIZE must be positive")
        return errors


@dataclass
class AnalysisConfig:
    """Forensic analysis configuration."""
    max_hops: int = field(default_factory=lambda: int(os.getenv("MAX_HOPS", "3")))
    min_amount_threshold: float = field(
        default_factory=lambda: float(os.getenv("MIN_AMOUNT_THRESHOLD", "0.00001"))  # FILTRO ANTI-DUST
    )
    btc_threshold: float = field(
        default_factory=lambda: float(os.getenv("BTC_THRESHOLD", "0.01"))  # Para filtering de transacciones pequeñas
    )
    
    def validate(self) -> List[str]:
        """Validate analysis configuration."""
        errors = []
        if self.max_hops <= 0:
            errors.append("MAX_HOPS must be positive")
        if self.min_amount_threshold < 0:
            errors.append("MIN_AMOUNT_THRESHOLD must be non-negative")
        if self.btc_threshold < 0:
            errors.append("BTC_THRESHOLD must be non-negative")
        return errors


@dataclass
class LoggingConfig:
    """Logging configuration."""
    verbose: bool = field(default_factory=lambda: os.getenv("VERBOSE", "true").lower() == "true")
    level: LogLevel = field(
        default_factory=lambda: LogLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    )
    
    def validate(self) -> List[str]:
        """Validate logging configuration."""
        errors = []
        try:
            LogLevel(self.level.value)
        except ValueError:
            errors.append(f"Invalid LOG_LEVEL: {self.level.value}. Must be one of: {[l.value for l in LogLevel]}")
        return errors


@dataclass
class OutputConfig:
    """Output directories configuration."""
    reports_dir: str = field(default_factory=lambda: os.getenv("REPORTS_DIR", "reports"))
    export_dir: str = field(default_factory=lambda: os.getenv("EXPORT_DIR", "exports"))
    
    def validate(self) -> List[str]:
        """Validate output configuration."""
        errors = []
        # These are directories, so we just check they're not empty strings
        if not self.reports_dir:
            errors.append("REPORTS_DIR cannot be empty")
        if not self.export_dir:
            errors.append("EXPORT_DIR cannot be empty")
        return errors


@dataclass
class Config:
    """Main configuration container."""
    neo4j: Neo4jConfig = field(default_factory=Neo4jConfig)
    api: APIConfig = field(default_factory=APIConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    
    def validate(self) -> List[str]:
        """Validate all configuration sections."""
        errors = []
        errors.extend(self.neo4j.validate())
        errors.extend(self.api.validate())
        errors.extend(self.analysis.validate())
        errors.extend(self.logging.validate())
        errors.extend(self.output.validate())
        return errors
    
    def is_valid(self) -> bool:
        """Check if configuration is valid."""
        return len(self.validate()) == 0
    
    def get_validation_errors(self) -> str:
        """Get validation errors as a formatted string."""
        errors = self.validate()
        if not errors:
            return "Configuration is valid"
        return "Configuration errors:\n" + "\n".join(f"  - {error}" for error in errors)