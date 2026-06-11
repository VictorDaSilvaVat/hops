"""
Domain model for a blockchain address (BTC, ETH, etc.).
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from enum import Enum


class EntityType(Enum):
    """Types of blockchain entities."""
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
    """Blockchain address domain model (multi-chain)."""
    address: str
    wallet_id: Optional[str] = None
    chain: str = "btc"
    decimals: int = 8
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
    def total_received_native(self) -> float:
        """Total received in native unit (BTC or ETH)."""
        return self.total_received_satoshis / (10 ** self.decimals)

    @property
    def total_sent_native(self) -> float:
        """Total sent in native unit (BTC or ETH)."""
        return self.total_sent_satoshis / (10 ** self.decimals)

    @property
    def balance_native(self) -> float:
        """Balance in native unit (BTC or ETH)."""
        return self.balance_satoshis / (10 ** self.decimals)

    @property
    def total_received_btc(self) -> float:
        return self.total_received_native

    @property
    def total_sent_btc(self) -> float:
        return self.total_sent_native

    @property
    def balance_btc(self) -> float:
        return self.balance_native

    @property
    def is_entity_known(self) -> bool:
        """Whether the entity type is known with reasonable confidence."""
        return self.entity_type != EntityType.UNKNOWN and self.entity_confidence > 0.3
