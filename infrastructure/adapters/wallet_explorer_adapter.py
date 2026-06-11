"""
Adapter for WalletExplorer API implementing the WalletAPI port.
"""
from typing import Optional, Dict, List, Any
import logging

from domain.ports.wallet_api import WalletAPI
from ..external.walletexplorer_client import WalletExplorerClient

logger = logging.getLogger(__name__)


class WalletExplorerAdapter(WalletAPI):
    """Adapter that makes WalletExplorerClient conform to WalletAPI port."""

    def __init__(self, wallet_explorer_client: Optional[WalletExplorerClient] = None):
        self.client = wallet_explorer_client or WalletExplorerClient()
        self.logger = logger

    def get_wallet_id(self, address: str) -> Optional[str]:
        """
        Get wallet ID (cluster identifier) for a Bitcoin address from WalletExplorer.

        Args:
            address: Bitcoin address string

        Returns:
            Wallet ID string or None if not found/error
        """
        try:
            self.logger.debug("Getting wallet ID for %s from WalletExplorer", address)
            return self.client.get_wallet_id(address)
        except Exception as e:
            self.logger.error("Error getting wallet ID from WalletExplorer for %s: %s", address, e)
            return None

    def get_wallet_info(self, wallet_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a wallet/entity from WalletExplorer.

        Args:
            wallet_id: Wallet identifier

        Returns:
            Dictionary with wallet information or None if not found/error
        """
        try:
            self.logger.debug("Getting wallet info for %s from WalletExplorer", wallet_id)
            return self.client.get_wallet_info(wallet_id)
        except Exception as e:
            self.logger.error("Error getting wallet info from WalletExplorer for %s: %s", wallet_id, e)
            return None

    def get_wallet_addresses(self, wallet_id: str, limit: int = 2000) -> List[str]:
        """
        Get addresses belonging to a wallet from WalletExplorer.

        Args:
            wallet_id: Wallet identifier
            limit: Maximum number of addresses to return

        Returns:
            List of Bitcoin addresses
        """
        try:
            self.logger.debug(f"Getting wallet addresses for {wallet_id} from WalletExplorer (limit: {limit})")
            addresses = self.client.get_wallet_addresses(wallet_id, limit=limit)
            # Ensure we return a list of strings
            return [addr for addr in addresses if isinstance(addr, str)]
        except Exception as e:
            self.logger.error(f"Error getting wallet addresses for {wallet_id} from WalletExplorer: {e}")
            return []