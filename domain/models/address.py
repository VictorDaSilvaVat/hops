"""
Domain model for a Bitcoin address.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from enum import Enum


class EntityType(Enum):
    """Types of Bitcoin entities."""
    EXCHANGE = "exchange"
    MIXER = "mixer"
    MINING_POOL = "mining_pool"
    WALLET_SERVICE = "wallet_service"
    MARKETPLACE = "marketplace"
    GAMBLING = "gambling"
    DARKNET_MARKET = "darknet_market"
    SANCTIONED = "sanctioned"
    DEFI_PROTOCOL = "defi_protocol"
    BRIDGE = "bridge"
    INDIVIDUAL = "individual"
    UNKNOWN = "unknown"


@dataclass
class Address:
    """Bitcoin address domain model."""
    address: str
    wallet_id: Optional[str] = None
    entity_type: EntityType = EntityType.UNKNOWN
    entity_confidence: float = 0.0
    labels: List[str] = field(default_factory=list)
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    transaction_count: int = 0
    total_received_satoshis: int = 0
    total_sent_satoshis: int = 0
    balance_satoshis: int = 0
    is_contract: bool = False
    tags: List[str] = field(default_factory=list)
    
    @property
    def total_received_btc(self) -> float:
        """Total received in BTC."""
        return self.total_received_satoshis / 100_000_000
    
    @property
    def total_sent_btc(self) -> float:
        """Total sent in BTC."""
        return self.total_sent_satoshis / 100_000_000
    
    @property
    def balance_btc(self) -> float:
        """Balance in BTC."""
        return self.balance_satoshis / 100_000_000
    
    @property
    def is_entity_known(self) -> bool:
        """Whether the entity type is known with reasonable confidence."""
        return self.entity_type != EntityType.UNKNOWN and self.entity_confidence > 0.3