"""
Adapter for TRONGRID API (TRX) implementing the BlockchainAPI port.
TRX is account-based, so we follow the ETH pattern.
"""
import hashlib
import base58
from typing import Optional, Dict, List, Any
import logging

from domain.ports.blockchain_api import BlockchainAPI
from ..external.trongrid_client import TronGridClient
from exceptions import RateLimitError
import time

logger = logging.getLogger(__name__)


def hex_to_base58(hex_addr: str) -> Optional[str]:
    """Convert TRON hex address (41... or 0x41...) to base58 (T...)."""
    if not hex_addr:
        return None
    h = hex_addr.strip()
    if h.startswith("0x"):
        h = h[2:]
    # Full hex address should be 42 chars (41 prefix + 40 hex)
    if len(h) != 42:
        return None
    raw = bytes.fromhex(h)
    checksum = hashlib.sha256(hashlib.sha256(raw).digest()).digest()[:4]
    return base58.b58encode(raw + checksum).decode()


def extract_base58(hex_addr: str) -> Optional[str]:
    """Extract base58 address from hex, handling errors gracefully."""
    try:
        return hex_to_base58(hex_addr)
    except Exception as e:
        logger.debug(f"Failed to convert hex address {hex_addr}: {e}")
        return None


class TronGridAdapter(BlockchainAPI):
    """Adapter for TRONGRID API implementing BlockchainAPI port."""

    def __init__(self, trongrid_client: Optional[TronGridClient] = None):
        self.client = trongrid_client or TronGridClient()
        self.logger = logger

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

    def get_address_info(self, address: str, chain: str = "trx") -> Optional[Dict[str, Any]]:
        try:
            self.logger.debug(f"Getting TRX account info for {address}")
            data = self.client.get_account_info(address)
            if not data:
                return None

            accounts = data.get("data", [])
            if not accounts:
                return {"address": address, "tx_count": 0, "balance": 0,
                        "chain_stats": {"funded_txo_sum": 0, "spent_txo_sum": 0},
                        "mempool_stats": {"funded_txo_sum": 0, "spent_txo_sum": 0}}

            acct = accounts[0]
            balance_sun = self._safe_int(acct.get("balance", 0))

            return {
                "address": address,
                "tx_count": 0,
                "balance": balance_sun,
                "chain_stats": {
                    "funded_txo_sum": balance_sun,
                    "spent_txo_sum": 0,
                },
                "mempool_stats": {
                    "funded_txo_sum": 0,
                    "spent_txo_sum": 0,
                },
                "_raw": acct,
            }
        except Exception as e:
            self.logger.error(f"Error getting TRX account info for {address}: {e}")
            return None

    def get_transaction(self, txid: str, chain: str = "trx") -> Optional[Dict[str, Any]]:
        try:
            self.logger.debug(f"Getting TRX transaction {txid}")
            data = self.client.get_transaction(txid)
            if not data:
                return None
            return self._normalize_tx(data)
        except RateLimitError as e:
            self.logger.warning(f"Rate limit on tx {txid}, retrying...")
            time.sleep(e.retry_after or 2)
            try:
                data = self.client.get_transaction(txid)
                return self._normalize_tx(data) if data else None
            except Exception as e2:
                self.logger.error(f"Retry failed for tx {txid}: {e2}")
                return None
        except Exception as e:
            self.logger.error(f"Error getting TRX transaction {txid}: {e}")
            return None

    def get_transaction_inputs(self, txid: str, chain: str = "trx") -> List[Dict[str, Any]]:
        tx = self.get_transaction(txid, chain=chain)
        if tx and tx.get("from"):
            return [{"address": tx["from"], "value": tx.get("value", 0)}]
        return []

    def get_transaction_outputs(self, txid: str, chain: str = "trx") -> List[Dict[str, Any]]:
        tx = self.get_transaction(txid, chain=chain)
        if tx and tx.get("to"):
            return [{"address": tx["to"], "value": tx.get("value", 0)}]
        return []

    def _normalize_contract_tx(self, tx: Dict) -> Optional[Dict]:
        """Normalize a TRON transaction to unified format.
        Handles TransferContract and TriggerSmartContract with TRX value.
        """
        raw = tx.get("raw_data", {})
        contracts = raw.get("contract", [])
        if not contracts:
            return None

        c = contracts[0]
        ctype = c.get("type", "")
        pv = c.get("parameter", {}).get("value", {})

        if ctype == "TransferContract":
            owner_hex = pv.get("owner_address", "")
            to_hex = pv.get("to_address", "")
            amount = self._safe_int(pv.get("amount", 0))

            owner_b58 = extract_base58(owner_hex)
            to_b58 = extract_base58(to_hex)
            if not owner_b58 or not to_b58:
                return None

            return {
                "txid": tx.get("txID", ""),
                "from": owner_b58,
                "to": to_b58,
                "value": amount,
                "timeStamp": raw.get("timestamp", 0),
                "block_number": tx.get("blockNumber", 0),
                "block_timestamp": tx.get("block_timestamp", 0),
                "tx_type": "transfer",
                "token": None,
                "ret": tx.get("ret", [{}])[0].get("contractRet", ""),
            }

        if ctype == "TriggerSmartContract":
            owner_hex = pv.get("owner_address", "")
            amount = self._safe_int(pv.get("amount", 0))
            if amount <= 0:
                return None  # No TRX transferred, only contract interaction
            contract_hex = pv.get("contract_address", "")
            to_b58 = extract_base58(contract_hex)
            owner_b58 = extract_base58(owner_hex)
            if not owner_b58 or not to_b58:
                return None
            return {
                "txid": tx.get("txID", ""),
                "from": owner_b58,
                "to": to_b58,
                "value": amount,
                "timeStamp": raw.get("timestamp", 0),
                "block_number": tx.get("blockNumber", 0),
                "block_timestamp": tx.get("block_timestamp", 0),
                "tx_type": "transfer",
                "token": None,
                "ret": tx.get("ret", [{}])[0].get("contractRet", ""),
            }

        return None

    def _normalize_trc20(self, tx: Dict) -> Dict:
        """Normalize a TRC20 transfer to unified format."""
        return {
            "txid": tx.get("transaction_id", ""),
            "from": tx.get("from", ""),
            "to": tx.get("to", ""),
            "value": self._safe_int(tx.get("value", 0)),
            "timeStamp": tx.get("block_timestamp", 0),
            "block_number": 0,
            "block_timestamp": tx.get("block_timestamp", 0),
            "tx_type": "trc20",
            "token": tx.get("token_info", {}).get("symbol", "TRC20"),
            "token_address": tx.get("token_info", {}).get("address", ""),
            "token_decimals": tx.get("token_info", {}).get("decimals", 6),
            "ret": "SUCCESS",
        }

    def _normalize_tx(self, tx: Dict) -> Optional[Dict]:
        """Try to normalize a transaction from any endpoint."""
        return self._normalize_contract_tx(tx)

    def get_address_transactions(self, address: str, limit: int = 200,
                                 chain: str = "trx") -> List[Dict[str, Any]]:
        try:
            self.logger.debug(f"Getting TRX transactions for {address} (limit={limit})")
            result = []

            # Fetch native TRX transfers (TransferContract)
            raw_txs = self.client.get_account_transactions(address, limit=limit)
            for tx in raw_txs:
                normalized = self._normalize_contract_tx(tx)
                if normalized:
                    result.append(normalized)

            # Fetch TRC20 transfers
            trc20_limit = max(10, limit - len(result))
            raw_trc20 = self.client.get_account_trc20(address, limit=trc20_limit)
            for tx in raw_trc20:
                normalized = self._normalize_trc20(tx)
                result.append(normalized)

            # Sort by timestamp (newest first)
            result.sort(key=lambda x: x.get("timeStamp", 0), reverse=True)

            return result[:limit]

        except RateLimitError as e:
            self.logger.warning(f"Rate limit on TRX txs for {address}, retrying...")
            time.sleep(e.retry_after or 2)
            try:
                return self.get_address_transactions(address, limit=limit)
            except Exception as e2:
                self.logger.error(f"Retry failed for TRX txs {address}: {e2}")
                return []
        except Exception as e:
            self.logger.error(f"Error getting TRX transactions for {address}: {e}")
            return []
