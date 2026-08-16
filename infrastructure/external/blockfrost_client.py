"""
Blockfrost API client for Cardano blockchain.
Blockfrost is a commercial API with high reliability.
Requires API key (free tier available at blockfrost.io).
"""
import logging
from typing import Optional, List, Dict, Any

from base_api_client import BaseAPIClient

logger = logging.getLogger(__name__)


class BlockfrostClient(BaseAPIClient):
    """Blockfrost API client for Cardano blockchain data."""

    def __init__(
        self,
        project_id: str,
        base_url: str = "https://cardano-mainnet.blockfrost.io/api/v0",
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        rate_limit_delay: float = 0.1,
    ):
        headers = {
            "Content-Type": "application/json",
            "project_id": project_id,
        }

        super().__init__(
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            retry_delay=retry_delay,
            rate_limit_delay=rate_limit_delay,
        )
        self.session.headers.update(headers)

    # --- Address Endpoints ---

    def get_address_info(self, address: str) -> Optional[Dict[str, Any]]:
        """Get address information including balance and stake address."""
        try:
            result = self._get(f"/addresses/{address}")
            if not result:
                return None

            # Calculate total ADA balance from utxos
            total_lovelaces = sum(int(utxo.get("quantity", 0)) for utxo in result.get("amount", [])
                                 if utxo.get("unit") == "lovelace")

            return {
                "address": address,
                "balance_lovelaces": total_lovelaces,
                "balance_ada": total_lovelaces / 1_000_000.0,
                "stake_address": result.get("stake_address"),
                "tx_count": result.get("tx_count", 0),
                "received_sum": sum(int(utxo.get("quantity", 0)) for utxo in result.get("received_sum", [])
                                   if utxo.get("unit") == "lovelace"),
                "sent_sum": sum(int(utxo.get("quantity", 0)) for utxo in result.get("sent_sum", [])
                               if utxo.get("unit") == "lovelace"),
            }
        except Exception as e:
            logger.error(f"Error getting address info for {address}: {e}")
            return None

    def get_address_transactions(
        self, address: str, limit: int = 200, page: int = 1
    ) -> List[Dict[str, Any]]:
        """Get transactions for an address."""
        try:
            params = {"page": page, "count": min(limit, 100)}
            result = self._get(f"/addresses/{address}/transactions", params=params)
            if not isinstance(result, list):
                return []
            return result[:limit]
        except Exception as e:
            logger.error(f"Error getting address transactions for {address}: {e}")
            return []

    def get_address_utxos(self, address: str) -> List[Dict[str, Any]]:
        """Get UTxOs for an address."""
        try:
            result = self._get(f"/addresses/{address}/utxos")
            if isinstance(result, list):
                return result
            return []
        except Exception as e:
            logger.error(f"Error getting address UTxOs for {address}: {e}")
            return []

    def get_address_details(self, address: str) -> Optional[Dict[str, Any]]:
        """Get detailed address info including balance and stake address."""
        try:
            return self._get(f"/addresses/{address}")
        except Exception as e:
            logger.error(f"Error getting address details for {address}: {e}")
            return None

    # --- Transaction Endpoints ---

    def get_transaction(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        """Get detailed transaction information."""
        try:
            return self._get(f"/txs/{tx_hash}")
        except Exception as e:
            logger.error(f"Error getting transaction {tx_hash}: {e}")
            return None

    def get_transaction_utxos(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        """Get UTxOs for a specific transaction."""
        try:
            return self._get(f"/txs/{tx_hash}/utxos")
        except Exception as e:
            logger.error(f"Error getting transaction UTxOs for {tx_hash}: {e}")
            return None

    def get_transaction_metadata(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        """Get transaction metadata."""
        try:
            return self._get(f"/txs/{tx_hash}/metadata")
        except Exception as e:
            logger.error(f"Error getting transaction metadata for {tx_hash}: {e}")
            return None

    # --- Account/Stake Endpoints ---

    def get_account_addresses(self, stake_address: str, page: int = 1) -> List[Dict[str, Any]]:
        """Get all payment addresses associated with a stake address."""
        try:
            params = {"page": page, "count": 100}
            result = self._get(f"/accounts/{stake_address}/addresses", params=params)
            if isinstance(result, list):
                return result
            return []
        except Exception as e:
            logger.error(f"Error getting account addresses for {stake_address}: {e}")
            return []

    def get_account_info(self, stake_address: str) -> Optional[Dict[str, Any]]:
        """Get stake account information (rewards, delegation, etc.)."""
        try:
            return self._get(f"/accounts/{stake_address}")
        except Exception as e:
            logger.error(f"Error getting account info for {stake_address}: {e}")
            return None

    # --- Network Info ---

    def get_network_info(self) -> Optional[Dict[str, Any]]:
        """Get current network tip and epoch info."""
        try:
            return self._get("/network")
        except Exception as e:
            logger.error(f"Error getting network info: {e}")
            return None

    def get_latest_block(self) -> Optional[Dict[str, Any]]:
        """Get latest block."""
        try:
            result = self._get("/blocks/latest")
            if isinstance(result, list) and len(result) > 0:
                return result[0]
            return result if isinstance(result, dict) else None
        except Exception as e:
            logger.error(f"Error getting latest block: {e}")
            return None


def _from_lovelaces(lovelaces: int) -> float:
    """Convert lovelaces to ADA float."""
    return lovelaces / 1_000_000.0


def _sum_ada_from_amount(amount_list: List[Dict[str, Any]]) -> int:
    """Sum ADA (lovelaces) from Blockfrost amount list."""
    total = 0
    for item in amount_list:
        if item.get("unit") == "lovelace":
            total += int(item.get("quantity", 0))
    return total


def _extract_assets_from_amount(amount_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract native assets (non-ADA) from Blockfrost amount list."""
    assets = []
    for item in amount_list:
        if item.get("unit") != "lovelace":
            unit = item.get("unit", "")
            assets.append({
                "policy_id": unit[:56] if len(unit) >= 56 else "",
                "asset_name": unit[56:] if len(unit) > 56 else "",
                "quantity": item.get("quantity", "0"),
            })
    return assets