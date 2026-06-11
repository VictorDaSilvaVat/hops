"""
Service for analyzing transaction patterns and clustering addresses.
"""
from typing import List, Set, Dict, Any, Optional
from datetime import datetime
import logging
import math

from ...models.address import Address, EntityType
from ...models.analysis.cluster import TransactionCluster
from ...entity_recognizer import entity_recognizer

logger = logging.getLogger(__name__)


class ClusterAnalyzerService:
    """Service for analyzing transaction patterns and identifying clusters."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # Risk weights for different entity types
        self.entity_risk_weights = {
            EntityType.SANCTIONED.value: 1.0,
            EntityType.DARKNET_MARKET.value: 0.9,
            EntityType.MIXER.value: 0.8,
            EntityType.GAMBLING.value: 0.6,
            EntityType.EXCHANGE.value: 0.3,  # Legitimate but regulated
            EntityType.DEFI_PROTOCOL.value: 0.4,
            EntityType.BRIDGE.value: 0.5,
            EntityType.MINING_POOL.value: 0.2,
            EntityType.WALLET_SERVICE.value: 0.3,
            EntityType.MARKETPLACE.value: 0.4,
            EntityType.INDIVIDUAL.value: 0.1,
            EntityType.UNKNOWN.value: 0.5
        }

    def analyze_transaction_patterns(self, transactions: List[Dict[str, Any]]) -> List[TransactionCluster]:
        """
        Analyze a list of transactions to identify clusters and patterns.

        Args:
            transactions: List of transaction dictionaries with standard fields

        Returns:
            List of identified transaction clusters
        """
        self.logger.info(f"Analyzing {len(transactions)} transactions for patterns")

        # Group transactions by time windows and address relationships
        clusters = self._identify_clusters(transactions)

        # Enrich clusters with entity information
        self._enrich_clusters_with_entities(clusters)

        # Calculate risk scores
        for cluster in clusters:
            cluster.calculate_risk_score(self.entity_risk_weights)

        self.logger.info(f"Identified {len(clusters)} transaction clusters")
        return clusters

    def _identify_clusters(self, transactions: List[Dict[str, Any]]) -> List[TransactionCluster]:
        """Identify clusters based on transaction patterns and timing."""
        clusters = []
        
        # Simple clustering by time gaps and address relationships
        # Sort transactions by time
        sorted_txs = sorted(transactions, key=lambda x: x.get('block_time', 0))
        
        if not sorted_txs:
            return clusters

        current_cluster = TransactionCluster(
            cluster_id=f"cluster_{len(clusters)}_{datetime.now().timestamp()}"
        )
        
        prev_time = None
        TIME_GAP_THRESHOLD = 3600 * 24 * 7  # 1 week in seconds
        
        for tx in sorted_txs:
            tx_time = tx.get('block_time', 0)
            if tx_time == 0:
                continue
                
            tx_datetime = datetime.fromtimestamp(tx_time)
            
            # Check if this transaction belongs to current cluster
            if prev_time is not None:
                time_gap = tx_time - prev_time
                if time_gap > TIME_GAP_THRESHOLD:
                    # Start new cluster
                    if current_cluster.transaction_count > 0:
                        clusters.append(current_cluster)
                    current_cluster = TransactionCluster(
                        cluster_id=f"cluster_{len(clusters)}_{datetime.now().timestamp()}"
                    )
            
            # Add transaction to current cluster
            amount_btc = tx.get('amount', 0.0)
            current_cluster.add_transaction(amount_btc, tx_datetime)
            
            # Add addresses involved
            from_addr = tx.get('from_address')
            to_addr = tx.get('to_address')
            if from_addr:
                current_cluster.add_address(from_addr)
            if to_addr:
                current_cluster.add_address(to_addr)
            
            prev_time = tx_time
        
        # Add the last cluster
        if current_cluster.transaction_count > 0:
            clusters.append(current_cluster)
        
        return clusters

    def _enrich_clusters_with_entities(self, clusters: List[TransactionCluster]):
        """Enrich clusters with entity information from addresses."""
        for cluster in clusters:
            # For each address in the cluster, try to get entity information
            # Note: In a real implementation, we would batch these requests
            # For now, we'll use a simplified approach
            
            entity_types_found = set()
            for address in list(cluster.addresses)[:10]:  # Limit to avoid too many API calls
                try:
                    # This would normally call external services
                    # For now, we'll skip actual API calls to avoid external dependencies
                    # In practice, this would use the address analyzer service
                    pass
                except Exception as e:
                    self.logger.debug(f"Could not get entity info for {address}: {e}")
                    continue
            
            # If we couldn't get real entity data, we'll mark as unknown
            # In production, this would be populated with real data
            if not entity_types_found:
                cluster.add_entity_type("unknown")

    def detect_mixing_patterns(self, transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Detect potential mixing/tumbling patterns in transactions.

        Args:
            transactions: List of transaction dictionaries

        Returns:
            Dictionary with mixing analysis results
        """
        if not transactions:
            return {"is_mixing": False, "confidence": 0.0, "indicators": []}

        indicators = []
        confidence = 0.0

        # Analyze transaction values
        amounts = [tx.get('amount', 0.0) for tx in transactions if tx.get('amount')]
        if len(amounts) >= 5:
            # Check for many similar sized transactions (potential mixing)
            avg_amount = sum(amounts) / len(amounts)
            if avg_amount > 0:
                std_dev = math.sqrt(sum((x - avg_amount) ** 2 for x in amounts) / len(amounts))
                cv = std_dev / avg_amount if avg_amount > 0 else 0  # Coefficient of variation
                
                # Low CV suggests similar transaction sizes (potential mixing)
                if cv < 0.3 and len(amounts) >= 10:
                    indicators.append("low_value_variation")
                    confidence += 0.3

        # Analyze timing patterns
        timestamps = [tx.get('block_time', 0) for tx in transactions if tx.get('block_time')]
        if len(timestamps) >= 5:
            sorted_ts = sorted(timestamps)
            gaps = [sorted_ts[i+1] - sorted_ts[i] for i in range(len(sorted_ts)-1)]
            if gaps:
                avg_gap = sum(gaps) / len(gaps)
                # Regular timing might indicate automated mixing
                if avg_gap > 0:
                    gap_std = math.sqrt(sum((g - avg_gap) ** 2 for g in gaps) / len(gaps))
                    gap_cv = gap_std / avg_gap if avg_gap > 0 else 0
                    if gap_cv < 0.4:
                        indicators.append("regular_timing")
                        confidence += 0.2

        # Analyze address diversity
        from_addrs = set(tx.get('from_address') for tx in transactions if tx.get('from_address'))
        to_addrs = set(tx.get('to_address') for tx in transactions if tx.get('to_address'))
        unique_addresses = len(from_addrs.union(to_addrs))
        
        if len(transactions) >= 10 and unique_addresses < len(transactions) * 0.5:
            indicators.append("address_reuse")
            confidence += 0.2

        # Normalize confidence
        confidence = min(1.0, confidence)

        return {
            "is_mixing": confidence > 0.5,
            "confidence": confidence,
            "indicators": indicators
        }

    def detect_peeling_chain(self, transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Detect peeling chain patterns (common in theft/laundering).

        Args:
            transactions: List of transaction dictionaries

        Returns:
            Dictionary with peeling chain analysis results
        """
        if len(transactions) < 3:
            return {"is_peeling_chain": False, "confidence": 0.0, "chain_length": 0}

        # Sort by time
        sorted_txs = sorted(transactions, key=lambda x: x.get('block_time', 0))
        
        # Look for chains where large amounts are split into smaller ones
        chains_found = []
        max_chain_length = 0

        for i in range(len(sorted_txs) - 2):
            # Start a potential chain
            chain = [sorted_txs[i]]
            current_amount = sorted_txs[i].get('amount', 0.0)
            
            for j in range(i + 1, len(sorted_txs)):
                next_amount = sorted_txs[j].get('amount', 0.0)
                time_diff = sorted_txs[j].get('block_time', 0) - sorted_txs[i].get('block_time', 0)
                
                # Check if this could be a peeling step:
                # 1. Next amount is smaller than current
                # 2. Time difference is reasonable (not too far apart)
                # 3. Addresses are different
                if (next_amount < current_amount * 0.9 and  # Next is significantly smaller
                    time_diff < 3600 * 24 * 7 and  # Within a week
                    sorted_txs[j].get('to_address') != sorted_txs[i].get('from_address')):
                    
                    chain.append(sorted_txs[j])
                    current_amount = next_amount
                else:
                    break
            
            if len(chain) >= 3:
                chains_found.append(chain)
                max_chain_length = max(max_chain_length, len(chain))

        confidence = min(1.0, max_chain_length / 10.0)  # Normalize to max 10 length

        return {
            "is_peeling_chain": len(chains_found) > 0,
            "confidence": confidence,
            "chain_length": max_chain_length,
            "chains_found": len(chains_found)
        }