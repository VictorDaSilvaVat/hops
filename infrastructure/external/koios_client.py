"""
Koios API client for Cardano blockchain.
Koios is a decentralized, open-source API layer for Cardano.
No API key required (optional for higher rate limits).
"""
import logging
from typing import Optional, List, Dict, Any

from base_api_client import BaseAPIClient

logger = logging.getLogger(__name__)


class KoiosClient(BaseAPIClient):
    """Koios API client for Cardano blockchain data."""

    def __init__(
        self,
        base_url: str = "https://api.koios.rest/api/v1",
        api_key: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        rate_limit_delay: float = 0.3,
    ):
        super().__init__(
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            retry_delay=retry_delay,
            rate_limit_delay=rate_limit_delay,
        )
        # Set default headers after parent init
        self.session.headers.update({"Content-Type": "application/json"})
        if api_key:
            self.session.headers.update({"Authorization": f"Bearer {api_key}"})

    # --- Address Endpoints ---

    def get_address_info(self, address: str) -> Optional[Dict[str, Any]]:
        """Get address information including balance and stake address."""
        try:
            # Koios expects array of addresses
            payload = {"_addresses": [address]}
            result = self._post("/address_info", json=payload)
            if result and isinstance(result, list) and len(result) > 0:
                return result[0]
            return None
        except Exception as e:
            logger.error(f"Error getting address info for {address}: {e}")
            return None

    def get_address_transactions(
        self, address: str, limit: int = 200, after_height: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get transactions for an address."""
        try:
            payload = {"_addresses": [address]}
            if after_height:
                payload["_after_block_height"] = after_height
            result = self._post("/address_txs", json=payload)
            if result and isinstance(result, list):
                # Sort by block_time descending (newest first)
                result.sort(key=lambda x: x.get("block_time", 0), reverse=True)
                return result[:limit]
            return []
        except Exception as e:
            logger.error(f"Error getting address transactions for {address}: {e}")
            return []

    def get_address_utxos(self, address: str) -> List[Dict[str, Any]]:
        """Get UTxOs for an address."""
        try:
            payload = {"_addresses": [address]}
            result = self._post("/address_utxos", json=payload)
            if result and isinstance(result, list):
                return result
            return []
        except Exception as e:
            logger.error(f"Error getting address UTxOs for {address}: {e}")
            return []

    def get_address_assets(self, address: str) -> List[Dict[str, Any]]:
        """Get native assets for an address."""
        try:
            payload = {"_addresses": [address]}
            result = self._post("/address_assets", json=payload)
            if result and isinstance(result, list):
                return result
            return []
        except Exception as e:
            logger.error(f"Error getting address assets for {address}: {e}")
            return []

    # --- Account/Stake Endpoints ---

    def get_account_addresses(self, stake_address: str) -> List[Dict[str, Any]]:
        """Get all payment addresses associated with a stake address."""
        try:
            payload = {"_stake_addresses": [stake_address]}
            result = self._post("/account_addresses", json=payload)
            if result and isinstance(result, list):
                return result
            return []
        except Exception as e:
            logger.error(f"Error getting account addresses for {stake_address}: {e}")
            return []

    def get_account_info(self, stake_address: str) -> Optional[Dict[str, Any]]:
        """Get stake account information (rewards, delegation, etc.)."""
        try:
            payload = {"_stake_addresses": [stake_address]}
            result = self._post("/account_info", json=payload)
            if result and isinstance(result, list) and len(result) > 0:
                return result[0]
            return None
        except Exception as e:
            logger.error(f"Error getting account info for {stake_address}: {e}")
            return None

    # --- Transaction Endpoints ---

    def get_transaction(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        """Get detailed transaction information."""
        try:
            payload = {"_tx_hashes": [tx_hash]}
            result = self._post("/tx_info", json=payload)
            if result and isinstance(result, list) and len(result) > 0:
                return result[0]
            return None
        except Exception as e:
            logger.error(f"Error getting transaction {tx_hash}: {e}")
            return None

    def get_transaction_utxos(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        """Get UTxOs for a specific transaction."""
        try:
            payload = {"_tx_hashes": [tx_hash]}
            result = self._post("/tx_utxos", json=payload)
            if result and isinstance(result, list) and len(result) > 0:
                return result[0]
            return None
        except Exception as e:
            logger.error(f"Error getting transaction UTxOs for {tx_hash}: {e}")
            return None

    # --- Network Info ---

    def get_network_info(self) -> Optional[Dict[str, Any]]:
        """Get current network tip and epoch info."""
        try:
            result = self._get("/tip")
            if result and isinstance(result, list) and len(result) > 0:
                return result[0]
            return None
        except Exception as e:
            logger.error(f"Error getting network info: {e}")
            return None

    def get_epoch_info(self, epoch_no: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Get epoch information."""
        try:
            endpoint = f"/epoch_info{'?epoch_no=' + str(epoch_no) if epoch_no else ''}"
            result = self._get(endpoint)
            if result and isinstance(result, list) and len(result) > 0:
                return result[0]
            return None
        except Exception as e:
            logger.error(f"Error getting epoch info: {e}")
            return None

    # --- Asset/Token Endpoints ---

    def get_asset_info(self, policy_id: str, asset_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get asset/token information."""
        try:
            payload = {"_asset_list": [f"{policy_id}{asset_name}" if asset_name else policy_id]}
            result = self._post("/asset_info", json=payload)
            if result and isinstance(result, list):
                return result
            return []
        except Exception as e:
            logger.error(f"Error getting asset info for {policy_id}: {e}")
            return []


def _to_lovelaces(amount_str: str) -> int:
    """Convert ADA string to lovelaces (1 ADA = 1,000,000 lovelaces)."""
    try:
        if "." in amount_str:
            ada, decimal = amount_str.split(".")
            decimal = (decimal + "000000")[:6]
            return int(ada) * 1_000_000 + int(decimal)
        return int(amount_str) * 1_000_000
    except Exception:
        return 0


def _from_lovelaces(lovelaces: int) -> float:
    """Convert lovelaces to ADA float."""
    return lovelaces / 1_000_000.0


def _sum_ada_from_value(value_list: List[Dict[str, Any]]) -> int:
    """Sum ADA (lovelaces) from a value list (UTxO value format)."""
    total = 0
    for item in value_list:
        if item.get("unit") == "lovelace":
            total += int(item.get("quantity", 0))
    return total


def _extract_assets_from_value(value_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract native assets (non-ADA) from a value list."""
    assets = []
    for item in value_list:
        if item.get("unit") != "lovelace":
            assets.append({
                "policy_id": item.get("unit")[:56],
                "asset_name": item.get("unit")[56:] if len(item.get("unit", "")) > 56 else "",
                "quantity": item.get("quantity", "0"),
                "fingerprint": item.get("fingerprint", ""),
            })
    return assets