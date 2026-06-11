"""
Service for analyzing Bitcoin addresses and transactions.
"""
from typing import Optional, List, Dict, Any, Set
from datetime import datetime
import logging

from ..models.address import Address, EntityType
from ..ports.blockchain_api import BlockchainAPI
from ..ports.wallet_api import WalletAPI
from ..entity_recognizer import entity_recognizer

logger = logging.getLogger(__name__)


class AddressAnalyzerService:
    """Service for analyzing Bitcoin addresses and their relationships."""

    def __init__(
        self,
        blockchain_api: BlockchainAPI,
        wallet_api: WalletAPI,
        min_amount_threshold: float = 0.00001
    ):
        self.blockchain_api = blockchain_api
        self.wallet_api = wallet_api
        self.min_amount_threshold = min_amount_threshold
        self.logger = logging.getLogger(__name__)

    def analyze_address(self, address: str) -> Address:
        """
        Analyze a Bitcoin address and return enriched address model.

        Args:
            address: Bitcoin address to analyze

        Returns:
            Address domain model with enriched data
        """
        self.logger.info(f"Analyzing address: {address}")

        # Get address info from blockchain API
        address_info = self.blockchain_api.get_address_info(address)
        if not address_info:
            self.logger.warning(f"No address info found for {address}")
            return Address(address=address)

        # Get wallet ID (cluster information)
        wallet_id = self.wallet_api.get_wallet_id(address)
        
        # Get wallet info if available
        wallet_info = None
        if wallet_id and wallet_id != "unknown":
            wallet_info = self.wallet_api.get_wallet_info(wallet_id)

        # Get address transactions
        transactions = self.blockchain_api.get_address_transactions(address)

        # Create address model
        addr_model = Address(
            address=address,
            wallet_id=wallet_id
        )

        # Populate basic info from address_info
        if address_info:
            addr_model.chain = address_info.get("chain", "BTC")
            addr_model.transaction_count = address_info.get("tx_count", 0)
            addr_model.total_received_satoshis = address_info.get("chain_stats", {}).get("funded_txo_sum", 0)
            addr_model.total_sent_satoshis = address_info.get("chain_stats", {}).get("spent_txo_sum", 0)
            addr_model.balance_satoshis = addr_model.total_received_satoshis - addr_model.total_sent_satoshis

        # Classify entity
        if wallet_id:
            entity_profile = entity_recognizer.recognize_entity(wallet_id, address, {
                "tx_count": addr_model.transaction_count,
                "total_received": addr_model.total_received_satoshis,
                "total_sent": addr_model.total_sent_satoshis,
                "first_seen": address_info.get("first_seen"),
                "last_seen": address_info.get("last_seen")
            })
            
            addr_model.entity_type = entity_profile.entity_type
            addr_model.entity_confidence = entity_profile.confidence
            addr_model.labels = entity_profile.labels
            addr_model.tags = entity_profile.metadata.get("labels", [])
            
            # Add label from wallet info if available
            if wallet_info and isinstance(wallet_info, dict) and wallet_info.get("label"):
                label = wallet_info.get("label")
                if label and label not in addr_model.labels:
                    addr_model.labels.append(label)

        # Set timestamps
        if address_info:
            if "first_seen" in address_info:
                addr_model.first_seen = datetime.fromtimestamp(address_info["first_seen"])
            if "last_seen" in address_info:
                addr_model.last_seen = datetime.fromtimestamp(address_info["last_seen"])

        self.logger.info(f"Address analysis complete for {address}: {addr_model.entity_type.value} (confidence: {addr_model.entity_confidence:.2f})")
        return addr_model

    def get_transaction_details(self, txid: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a transaction.

        Args:
            txid: Transaction ID

        Returns:
            Transaction details or None if not found
        """
        try:
            tx = self.blockchain_api.get_transaction(txid)
            if not tx:
                return None

            # Enhance with inputs and outputs
            inputs = self.blockchain_api.get_transaction_inputs(txid)
            outputs = self.blockchain_api.get_transaction_outputs(txid)

            tx["inputs"] = inputs
            tx["outputs"] = outputs
            
            return tx
        except Exception as e:
            self.logger.error(f"Error getting transaction details for {txid}: {e}")
            return None