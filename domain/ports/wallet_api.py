"""
Port (interface) for wallet/explorer data providers (e.g., WalletExplorer).
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, List, Any


class WalletAPI(ABC):
    """Abstract interface for wallet/explorer data providers."""

    @abstractmethod
    def get_wallet_id(self, address: str) -> Optional[str]:
        """
        Get wallet ID (cluster identifier) for a Bitcoin address.

        Args:
            address: Bitcoin address string

        Returns:
            Wallet ID string or None if not found/error
        """
        pass

    @abstractmethod
    def get_wallet_info(self, wallet_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a wallet/entity.

        Args:
            wallet_id: Wallet identifier

        Returns:
            Dictionary with wallet information or None if not found/error
        """
        pass

    @abstractmethod
    def get_wallet_addresses(self, wallet_id: str, limit: int = 2000) -> List[str]:
        """
        Get addresses belonging to a wallet.

        Args:
            wallet_id: Wallet identifier
            limit: Maximum number of addresses to return

        Returns:
            List of Bitcoin addresses
        """
        pass