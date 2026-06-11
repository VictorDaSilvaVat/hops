"""
Port (interface) for blockchain data providers (e.g., Blockstream).
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, List, Any


class BlockchainAPI(ABC):
    """Abstract interface for blockchain data providers."""

    @abstractmethod
    def get_address_info(self, address: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a Bitcoin address.

        Args:
            address: Bitcoin address string

        Returns:
            Dictionary with address information or None if not found/error
        """
        pass

    @abstractmethod
    def get_transaction(self, txid: str) -> Optional[Dict[str, Any]]:
        """
        Get a transaction by its ID.

        Args:
            txid: Transaction ID

        Returns:
            Dictionary with transaction data or None if not found/error
        """
        pass

    @abstractmethod
    def get_transaction_inputs(self, txid: str) -> List[Dict[str, Any]]:
        """
        Get inputs for a transaction.

        Args:
            txid: Transaction ID

        Returns:
            List of input dictionaries
        """
        pass

    @abstractmethod
    def get_transaction_outputs(self, txid: str) -> List[Dict[str, Any]]:
        """
        Get outputs for a transaction.

        Args:
            txid: Transaction ID

        Returns:
            List of output dictionaries
        """
        pass

    @abstractmethod
    def get_address_transactions(self, address: str, limit: int = 200) -> List[Dict[str, Any]]:
        """
        Get transactions for an address.

        Args:
            address: Bitcoin address
            limit: Maximum number of transactions to return

        Returns:
            List of transaction dictionaries
        """
        pass