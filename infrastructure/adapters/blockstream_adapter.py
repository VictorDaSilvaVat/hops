"""
Adapter for Blockstream API implementing the BlockchainAPI port.
"""
from typing import Optional, Dict, List, Any
import logging

from domain.ports.blockchain_api import BlockchainAPI
from ..external.blockstream_client import BlockstreamClient
from exceptions import RateLimitError
import time

logger = logging.getLogger(__name__)


class BlockstreamAdapter(BlockchainAPI):
    """Adapter that makes BlockstreamClient conform to BlockchainAPI port."""

    def __init__(self, blockstream_client: Optional[BlockstreamClient] = None):
        self.client = blockstream_client or BlockstreamClient()
        self.logger = logger

    def get_address_info(self, address: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a Bitcoin address from Blockstream.

        Args:
            address: Bitcoin address string

        Returns:
            Dictionary with address information or None if not found/error
        """
        try:
            self.logger.debug(f"Getting address info for {address} from Blockstream")
            return self.client.get_address_info(address)
        except Exception as e:
            self.logger.error(f"Error getting address info from Blockstream for {address}: {e}")
            return None

    def get_transaction(self, txid: str) -> Optional[Dict[str, Any]]:
        """
        Get a transaction by its ID from Blockstream.

        Args:
            txid: Transaction ID

        Returns:
            Dictionary with transaction data or None if not found/error
        """
        try:
            self.logger.debug(f"Getting transaction {txid} from Blockstream")
            return self.client.get_tx(txid)
        except RateLimitError as e:
            self.logger.warning(f"Rate limit hit getting transaction {txid}, waiting {e.retry_after}s and retrying...")
            time.sleep(e.retry_after or 2)
            try:
                return self.client.get_tx(txid)
            except Exception as e2:
                self.logger.error(f"Retry failed for transaction {txid}: {e2}")
                return None
        except Exception as e:
            self.logger.error(f"Error getting transaction {txid} from Blockstream: {e}")
            return None

    def get_transaction_inputs(self, txid: str) -> List[Dict[str, Any]]:
        """
        Get inputs for a transaction from Blockstream.

        Args:
            txid: Transaction ID

        Returns:
            List of input dictionaries
        """
        try:
            self.logger.debug(f"Getting transaction inputs for {txid} from Blockstream")
            return self.client.get_tx_inputs(txid)
        except Exception as e:
            self.logger.error(f"Error getting transaction inputs for {txid} from Blockstream: {e}")
            return []

    def get_transaction_outputs(self, txid: str) -> List[Dict[str, Any]]:
        """
        Get outputs for a transaction from Blockstream.

        Args:
            txid: Transaction ID

        Returns:
            List of output dictionaries
        """
        try:
            self.logger.debug(f"Getting transaction outputs for {txid} from Blockstream")
            return self.client.get_tx_outputs(txid)
        except Exception as e:
            self.logger.error(f"Error getting transaction outputs for {txid} from Blockstream: {e}")
            return []

    def get_address_transactions(self, address: str, limit: int = 200) -> List[Dict[str, Any]]:
        """
        Get transactions for an address from Blockstream.

        Args:
            address: Bitcoin address
            limit: Maximum number of transactions to return

        Returns:
            List of transaction dictionaries
        """
        try:
            self.logger.debug("Getting address transactions for %s from Blockstream (limit: %s)", address, limit)
            return self.client.get_address_txs(address, limit=limit)
        except RateLimitError as e:
            self.logger.warning("Rate limit hit getting transactions for %s, waiting %ds and retrying...", address, e.retry_after or 2)
            time.sleep(e.retry_after or 2)
            try:
                return self.client.get_address_txs(address, limit=limit)
            except Exception as e2:
                self.logger.error("Retry failed for address transactions %s: %s", address, e2)
                return []
        except Exception as e:
            self.logger.error("Error getting address transactions for %s from Blockstream: %s", address, e)
            return []