"""
Domain models for transaction clustering analysis.
"""
from dataclasses import dataclass, field
from typing import List, Set, Optional
from datetime import datetime
from ..address import Address


@dataclass
class TransactionCluster:
    """Represents a cluster of transactions that are likely related."""
    cluster_id: str
    addresses: Set[str] = field(default_factory=set)
    transaction_count: int = 0
    total_volume_btc: float = 0.0
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    entity_types: Set[str] = field(default_factory=set)
    risk_score: float = 0.0
    description: str = ""
    
    def add_address(self, address: str):
        self.addresses.add(address)
    
    def add_transaction(self, amount_btc: float, timestamp: datetime):
        self.transaction_count += 1
        self.total_volume_btc += amount_btc
        if self.first_seen is None or timestamp < self.first_seen:
            self.first_seen = timestamp
        if self.last_seen is None or timestamp > self.last_seen:
            self.last_seen = timestamp
    
    def add_entity_type(self, entity_type: str):
        self.entity_types.add(entity_type)
    
    def calculate_risk_score(self, entity_risk_weights: dict) -> float:
        """Calculate risk score based on entity types in the cluster."""
        if not self.entity_types:
            self.risk_score = 0.1  # Default low risk
            return self.risk_score
        
        # Weighted average of entity risk scores
        total_weight = 0.0
        weighted_sum = 0.0
        for entity_type in self.entity_types:
            weight = entity_risk_weights.get(entity_type, 0.5)
            # Simple weighting: each entity type contributes equally
            total_weight += 1.0
            weighted_sum += weight
        
        if total_weight > 0:
            self.risk_score = weighted_sum / total_weight
        else:
            self.risk_score = 0.1
        
        return self.risk_score