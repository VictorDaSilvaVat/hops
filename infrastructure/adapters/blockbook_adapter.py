"""
Adapter for Blockbook API (BCH) implementing the BlockchainAPI port.
Normalizes Blockbook response format to match Blockstream format.
"""
from typing import Optional, Dict, List, Any
import logging

from domain.ports.blockchain_api import BlockchainAPI
from ..external.blockbook_client import BlockbookClient
from exceptions import RateLimitError
import time

logger = logging.getLogger(__name__)


class BlockbookAdapter(BlockchainAPI):
    """Adapter that makes BlockbookClient conform to BlockchainAPI port."""

    def __init__(self, blockbook_client: Optional[BlockbookClient] = None):
        self.client = blockbook_client or BlockbookClient()
        self.logger = logger

    def _strip_prefix(self, addr: Optional[str]) -> Optional[str]:
        """Strip bitcoincash: prefix from BCH addresses for consistent comparison."""
        if addr and addr.startswith("bitcoincash:"):
            return addr[len("bitcoincash:"):]
        return addr

    @staticmethod
    def _safe_int(v, default=0):
        if isinstance(v, int):
            return v
        if isinstance(v, float):
            return int(v)
        try:
            return int(str(v).strip())
        except (ValueError, TypeError, AttributeError):
            return default

    def _normalize_tx(self, tx: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Blockbook tx format to Blockstream-like format."""
        normalized = dict(tx)

        # Normalize vin: Blockbook has addresses[], we need prevout.scriptpubkey_address
        normalized["vin"] = []
        for vin in tx.get("vin", []):
            addr = self._strip_prefix((vin.get("addresses") or [None])[0])
            normalized["vin"].append({
                "txid": vin.get("txid"),
                "vout": self._safe_int(vin.get("vout")),
                "prevout": {
                    "scriptpubkey_address": addr,
                },
                "value": self._safe_int(vin.get("value")),
                "isAddress": vin.get("isAddress", True),
            })

        # Normalize vout: Blockbook has addresses[], we need scriptpubkey_address
        normalized["vout"] = []
        for vout in tx.get("vout", []):
            addr = self._strip_prefix((vout.get("addresses") or [None])[0])
            normalized["vout"].append({
                "value": self._safe_int(vout.get("value")),
                "n": self._safe_int(vout.get("n")),
                "scriptpubkey_address": addr,
                "isAddress": vout.get("isAddress", True),
            })

        # Normalize timestamp: Blockbook has blockTime, we want status.block_time
        block_time = tx.get("blockTime")
        normalized["status"] = {
            "block_time": block_time,
            "confirmed": block_time is not None,
        }

        return normalized

    def get_address_info(self, address: str, chain: str = "bch") -> Optional[Dict[str, Any]]:
        try:
            self.logger.debug(f"Getting address info for {address} from Blockbook")
            data = self.client.get_address_info(address)
            if not data:
                return None

            # Normalize to Blockstream-like format (strip bitcoincash: prefix)
            # Blockbook returns string values for numbers; convert to int
            return {
                "address": self._strip_prefix(data.get("address", address)),
                "tx_count": data.get("txs", 0),
                "chain_stats": {
                    "funded_txo_sum": self._safe_int(data.get("totalReceived", 0)),
                    "spent_txo_sum": self._safe_int(data.get("totalSent", 0)),
                },
                "mempool_stats": {
                    "funded_txo_sum": 0,
                    "spent_txo_sum": 0,
                },
                "balance": self._safe_int(data.get("balance", 0)),
                "_original_cashaddr": data.get("address", address),
            }
        except Exception as e:
            self.logger.error(f"Error getting address info from Blockbook for {address}: {e}")
            return None

    def get_transaction(self, txid: str, chain: str = "bch") -> Optional[Dict[str, Any]]:
        try:
            self.logger.debug(f"Getting transaction {txid} from Blockbook")
            tx = self.client.get_tx(txid)
            if not tx:
                return None
            return self._normalize_tx(tx)
        except RateLimitError as e:
            self.logger.warning(f"Rate limit hit getting transaction {txid}, waiting {e.retry_after}s...")
            time.sleep(e.retry_after or 2)
            try:
                tx = self.client.get_tx(txid)
                return self._normalize_tx(tx) if tx else None
            except Exception as e2:
                self.logger.error(f"Retry failed for transaction {txid}: {e2}")
                return None
        except Exception as e:
            self.logger.error(f"Error getting transaction {txid} from Blockbook: {e}")
            return None

    def get_transaction_inputs(self, txid: str, chain: str = "bch") -> List[Dict[str, Any]]:
        try:
            self.logger.debug(f"Getting transaction inputs for {txid} from Blockbook")
            inputs = self.client.get_tx_inputs(txid)
            normalized = []
            for vin in inputs:
                addr = self._strip_prefix((vin.get("addresses") or [None])[0])
                normalized.append({
                    "txid": vin.get("txid"),
                    "vout": vin.get("vout"),
                    "prevout": {
                        "scriptpubkey_address": addr,
                    },
                    "value": vin.get("value"),
                })
            return normalized
        except Exception as e:
            self.logger.error(f"Error getting transaction inputs for {txid} from Blockbook: {e}")
            return []

    def get_transaction_outputs(self, txid: str, chain: str = "bch") -> List[Dict[str, Any]]:
        try:
            self.logger.debug(f"Getting transaction outputs for {txid} from Blockbook")
            outputs = self.client.get_tx_outputs(txid)
            normalized = []
            for vout in outputs:
                addr = self._strip_prefix((vout.get("addresses") or [None])[0])
                normalized.append({
                    "value": vout.get("value"),
                    "n": vout.get("n"),
                    "scriptpubkey_address": addr,
                })
            return normalized
        except Exception as e:
            self.logger.error(f"Error getting transaction outputs for {txid} from Blockbook: {e}")
            return []

    def get_address_transactions(self, address: str, limit: int = 200,
                                 chain: str = "bch") -> List[Dict[str, Any]]:
        try:
            self.logger.debug("Getting address transactions for %s from Blockbook (limit: %s)", address, limit)
            txs = self.client.get_address_txs(address, limit=limit)
            return [self._normalize_tx(tx) for tx in txs if tx]
        except RateLimitError as e:
            self.logger.warning("Rate limit hit getting transactions for %s, waiting %ds...", address, e.retry_after or 2)
            time.sleep(e.retry_after or 2)
            try:
                txs = self.client.get_address_txs(address, limit=limit)
                return [self._normalize_tx(tx) for tx in txs if tx]
            except Exception as e2:
                self.logger.error("Retry failed for address transactions %s: %s", address, e2)
                return []
        except Exception as e:
            self.logger.error("Error getting address transactions for %s from Blockbook: %s", address, e)
            return []
