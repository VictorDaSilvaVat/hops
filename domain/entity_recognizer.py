"""
Entity recognition and classification for Bitcoin forensic analysis.
"""
import logging
import re
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class EntityType(Enum):
    """Types of Bitcoin entities that can be identified."""
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
class EntityProfile:
    """Profile of a Bitcoin entity with metadata and confidence scores."""
    address: str
    entity_type: EntityType
    confidence: float  # 0.0 to 1.0
    labels: List[str]  # Known labels/tags
    metadata: Dict[str, any]  # Additional information
    first_seen: Optional[int] = None  # Timestamp
    last_seen: Optional[int] = None   # Timestamp
    transaction_count: int = 0
    total_volume_btc: float = 0.0


class EntityRecognizer:
    """
    Recognizes and classifies Bitcoin entities based on various heuristics
    and known patterns.
    """
    
    def __init__(self):
        # Known entity patterns (wallet IDs, address patterns, etc.)
        self._init_known_patterns()
        
        # Risk scoring weights
        self.risk_weights = {
            'sanctioned': 1.0,
            'darknet_market': 0.9,
            'mixer': 0.8,
            'gambling': 0.6,
            'exchange': 0.3,  # Legitimate but regulated
            'defi_protocol': 0.4,
            'bridge': 0.5,
            'mining_pool': 0.2,
            'wallet_service': 0.3,
            'marketplace': 0.4,
            'individual': 0.1,
            'unknown': 0.5
        }
    
    def _init_known_patterns(self):
        """Initialize known patterns for entity recognition."""
        # Exchange patterns (based on known wallet IDs and patterns)
        self.exchange_patterns = {
            'binance', 'coinbase', 'kraken', 'bitfinex', 'kucoin', 'okx',
            'huobi', 'gate', 'poloniex', 'bittrex', 'bitstamp', 'gemini',
            'crypto', 'circle', 'paybis', 'changelly', 'shapeshift'
        }
        
        # Mixer patterns
        self.mixer_patterns = {
            'tornado', 'wasabi', 'samourai', 'joinmarket', 'zerolink',
            'whirlpool', 'cashfusion', 'mixer', 'tumbling'
        }
        
        # Mining pool patterns
        self.mining_pool_patterns = {
            'antpool', 'f2pool', 'poolin', 'slush', 'btcc', 'btc.com',
            'viabtc', 'bitfury', 'ckpool', 'nemotron'
        }
        
        # Wallet service patterns
        self.wallet_service_patterns = {
            'blockchain', 'coinbase', 'xapo', 'circle', 'bread', 'mycelium',
            'electrum', 'wasabi', 'samourai', 'greenaddress', 'greenwallet'
        }
        
        # Gambling patterns
        self.gambling_patterns = {
            'satoshidice', 'bitcasino', 'fortunejack', 'mbit', 'betcoin',
            'velvet', 'cryptogames', 'dicebitcoin'
        }
        
        # Darknet market patterns
        self.darknet_market_patterns = {
            'silkroad', 'alphabay', 'hansa', 'dream', 'wallstreet',
            'valhalla', 'tochka', 'berlusconi'
        }
        
        # Sanctioned entities (OFAC, etc.)
        self.sanctioned_patterns = {
            'ofac', 'sdn', 'lazarus', 'garantex', 'blender.io',
            'sinbad', 'chipmixer'
        }
        
        # DeFi protocol patterns
        self.defi_patterns = {
            'uniswap', 'sushiswap', 'curve', 'balancer', 'aave', 'compound',
            'maker', 'yearn', 'synthetix', 'rave'
        }
        
        # Bridge patterns
        self.bridge_patterns = {
            'optimism', 'arbitrum', 'polygon', 'avalanche', 'wormhole',
            'multichain', 'synapse', 'connext', 'celer'
        }
        
        # Marketplace patterns
        self.marketplace_patterns = {
            'openbazaar', 'purse', 'bitify', 'glyph', 'cryptograffiti'
        }
    
    def recognize_entity(self, wallet_id: str, address: str = None, 
                        transaction_data: Dict = None) -> EntityProfile:
        """
        Recognize entity type based on wallet ID and other data.
        
        Args:
            wallet_id: Wallet identifier from blockchain explorer
            address: Bitcoin address (optional)
            transaction_data: Additional transaction data (optional)
            
        Returns:
            EntityProfile with classification and confidence
        """
        if not wallet_id or wallet_id == "unknown":
            return self._create_unknown_profile(address)
        
        wallet_id_lower = wallet_id.lower()
        
        # Check against known patterns
        entity_type, confidence = self._classify_by_patterns(wallet_id_lower)
        
        # Enhance with additional data if available
        if transaction_data:
            entity_type, confidence = self._enhance_with_transaction_data(
                entity_type, confidence, transaction_data
            )
        
        # Extract labels/metadata
        labels = self._extract_labels(wallet_id_lower)
        metadata = self._extract_metadata(wallet_id, address, transaction_data)
        
        # Calculate risk score
        risk_score = self.risk_weights.get(entity_type, 0.5)
        
        return EntityProfile(
            address=address or "",
            entity_type=entity_type,
            confidence=confidence,
            labels=labels,
            metadata=metadata,
            transaction_count=transaction_data.get('tx_count', 0) if transaction_data else 0,
            total_volume_btc=transaction_data.get('total_received', 0.0) / 1e8 if transaction_data else 0.0
        )
    
    def _classify_by_patterns(self, wallet_id: str) -> Tuple[EntityType, float]:
        """Classify entity based on known patterns."""
        # Check sanctioned first (highest priority)
        if any(pattern in wallet_id for pattern in self.sanctioned_patterns):
            return EntityType.SANCTIONED, 0.95
        
        # Check mixer patterns
        if any(pattern in wallet_id for pattern in self.mixer_patterns):
            return EntityType.MIXER, 0.9
        
        # Check exchange patterns
        if any(pattern in wallet_id for pattern in self.exchange_patterns):
            return EntityType.EXCHANGE, 0.85
        
        # Check mining pool patterns
        if any(pattern in wallet_id for pattern in self.mining_pool_patterns):
            return EntityType.MINING_POOL, 0.8
        
        # Check wallet service patterns
        if any(pattern in wallet_id for pattern in self.wallet_service_patterns):
            return EntityType.WALLET_SERVICE, 0.75
        
        # Check gambling patterns
        if any(pattern in wallet_id for pattern in self.gambling_patterns):
            return EntityType.GAMBLING, 0.8
        
        # Check darknet market patterns
        if any(pattern in wallet_id for pattern in self.darknet_market_patterns):
            return EntityType.DARKNET_MARKET, 0.9
        
        # Check DeFi patterns
        if any(pattern in wallet_id for pattern in self.defi_patterns):
            return EntityType.DEFI_PROTOCOL, 0.7
        
        # Check bridge patterns
        if any(pattern in wallet_id for pattern in self.bridge_patterns):
            return EntityType.BRIDGE, 0.75
        
        # Check marketplace patterns
        if any(pattern in wallet_id for pattern in self.marketplace_patterns):
            return EntityType.MARKETPLACE, 0.7
        
        # Default to individual with low confidence
        return EntityType.INDIVIDUAL, 0.3
    
    def _enhance_with_transaction_data(self, entity_type: EntityType, 
                                     confidence: float, 
                                     transaction_data: Dict) -> Tuple[EntityType, float]:
        """Enhance classification using transaction data patterns."""
        if not transaction_data:
            return entity_type, confidence
        
        # Analyze transaction patterns
        tx_count = transaction_data.get('tx_count', 0)
        total_received = transaction_data.get('total_received', 0)
        total_sent = transaction_data.get('total_sent', 0)
        
        # High volume + frequent transactions suggests exchange/service
        if tx_count > 1000 and total_received > 10000 * 1e8:  # >10k BTC
            if entity_type == EntityType.INDIVIDUAL:
                entity_type = EntityType.WALLET_SERVICE
                confidence = max(confidence, 0.7)
        
        # Many small transactions might indicate mixing
        if tx_count > 100:
            avg_tx_size = total_received / max(tx_count, 1)
            if avg_tx_size < 0.01 * 1e8:  # <0.01 BTC average
                if entity_type in [EntityType.INDIVIDUAL, EntityType.WALLET_SERVICE]:
                    entity_type = EntityType.MIXER
                    confidence = max(confidence, 0.6)
        
        # Adjust confidence based on data availability
        data_bonus = min(0.2, len(transaction_data) * 0.02)  # Up to 0.2 bonus
        confidence = min(1.0, confidence + data_bonus)
        
        return entity_type, confidence
    
    def _extract_labels(self, wallet_id: str) -> List[str]:
        """Extract meaningful labels from wallet ID."""
        labels = []
        
        # Add entity type as label
        for pattern_list, entity_type in [
            (self.exchange_patterns, EntityType.EXCHANGE),
            (self.mixer_patterns, EntityType.MIXER),
            (self.mining_pool_patterns, EntityType.MINING_POOL),
            (self.wallet_service_patterns, EntityType.WALLET_SERVICE),
            (self.gambling_patterns, EntityType.GAMBLING),
            (self.darknet_market_patterns, EntityType.DARKNET_MARKET),
            (self.sanctioned_patterns, EntityType.SANCTIONED),
            (self.defi_patterns, EntityType.DEFI_PROTOCOL),
            (self.bridge_patterns, EntityType.BRIDGE),
            (self.marketplace_patterns, EntityType.MARKETPLACE)
        ]:
            if any(pattern in wallet_id for pattern in pattern_list):
                labels.append(entity_type.value)
                break
        
        # Add specific service names if found
        known_services = {
            'binance': 'binance',
            'coinbase': 'coinbase',
            'kraken': 'kraken',
            'tornado': 'tornado_cash',
            'wasabi': 'wasabi_wallet',
            'samourai': 'samourai_wallet'
        }
        
        for service_id, label in known_services.items():
            if service_id in wallet_id:
                labels.append(label)
        
        return list(set(labels))  # Remove duplicates
    
    def _extract_metadata(self, wallet_id: str, address: str, 
                         transaction_data: Dict) -> Dict[str, any]:
        """Extract metadata for the entity profile."""
        metadata = {
            'wallet_id': wallet_id,
            'address': address,
            'recognized_at': int(time.time())
        }
        
        if transaction_data:
            metadata.update({
                'first_seen': transaction_data.get('first_seen'),
                'last_seen': transaction_data.get('last_seen'),
                'tx_count': transaction_data.get('tx_count'),
                'total_received_sat': transaction_data.get('total_received'),
                'total_sent_sat': transaction_data.get('total_sent'),
                'balance_sat': transaction_data.get('final_balance')
            })
        
        # Remove None values
        return {k: v for k, v in metadata.items() if v is not None}
    
    def _create_unknown_profile(self, address: str = None) -> EntityProfile:
        """Create a profile for unknown entities."""
        return EntityProfile(
            address=address or "",
            entity_type=EntityType.UNKNOWN,
            confidence=0.1,
            labels=["unknown"],
            metadata={"address": address} if address else {},
            transaction_count=0,
            total_volume_btc=0.0
        )
    
    def get_risk_score(self, entity_profile: EntityProfile) -> float:
        """
        Calculate risk score for an entity profile.
        
        Returns:
            Risk score from 0.0 (lowest) to 1.0 (highest)
        """
        base_risk = self.risk_weights.get(entity_profile.entity_type, 0.5)
        
        # Adjust based on confidence
        adjusted_risk = base_risk * (0.5 + 0.5 * entity_profile.confidence)
        
        # Adjust based on transaction volume (higher volume = higher risk for certain types)
        if entity_profile.entity_type in [EntityType.MIXER, EntityType.DARKNET_MARKET, EntityType.SANCTIONED]:
            volume_factor = min(2.0, 1.0 + (entity_profile.total_volume_btc / 1000))  # Cap at 2x
            adjusted_risk *= volume_factor
        
        return min(1.0, adjusted_risk)


# Global entity recognizer instance
entity_recognizer = EntityRecognizer()