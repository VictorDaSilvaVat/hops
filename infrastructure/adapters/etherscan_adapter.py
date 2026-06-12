"""
Adapter for Etherscan API V2 implementing the BlockchainAPI port for ETH.
"""
from typing import Optional, Dict, List, Any
import logging

from domain.ports.blockchain_api import BlockchainAPI
from ..external.etherscan_client import EtherscanClient

logger = logging.getLogger(__name__)


class EtherscanAdapter(BlockchainAPI):
    """Adapter that makes EtherscanClient conform to BlockchainAPI for Ethereum."""

    def __init__(self, api_key: str = "", etherscan_client: Optional[EtherscanClient] = None):
        self.client = etherscan_client or EtherscanClient(api_key=api_key)
        self.logger = logger

    def get_address_info(self, address: str, chain: str = "eth") -> Optional[Dict[str, Any]]:
        try:
            balance_resp = self.client.get_balance(address)
            balance = 0
            if balance_resp and balance_resp.get("status") == "1":
                try:
                    balance = int(balance_resp.get("result", 0))
                except (ValueError, TypeError):
                    balance = 0
            elif balance_resp and balance_resp.get("status") == "0":
                self.logger.warning(
                    f"Etherscan balance API error for {address}: {balance_resp.get('message', '')}"
                )
            tx_resp = self.client.get_address_txs(address)
            tx_count = 0
            if tx_resp and isinstance(tx_resp.get("result"), list):
                tx_count = len(tx_resp["result"])

            return {
                "address": address,
                "chain": "eth",
                "balance": balance,
                "tx_count": tx_count,
                "chain_stats": {
                    "funded_txo_sum": balance,
                    "spent_txo_sum": 0,
                },
            }
        except Exception as e:
            self.logger.error(f"Error getting address info for {address}: {e}")
            return None

    def get_transaction(self, txid: str, chain: str = "eth") -> Optional[Dict[str, Any]]:
        try:
            resp = self.client._call({
                "chainid": 1, "module": "proxy", "action": "eth_getTransactionByHash",
                "txhash": txid,
            })
            return resp
        except Exception as e:
            self.logger.error(f"Error getting transaction {txid}: {e}")
            return None

    def get_transaction_inputs(self, txid: str, chain: str = "eth") -> List[Dict[str, Any]]:
        return []

    def get_transaction_outputs(self, txid: str, chain: str = "eth") -> List[Dict[str, Any]]:
        return []

    def get_address_transactions(self, address: str, limit: int = 200,
                                 chain: str = "eth") -> List[Dict[str, Any]]:
        try:
            normal = self.client.get_address_txs(address, limit=limit)
            internal = self.client.get_address_internal_txs(address, limit=limit)
            erc20 = self.client.get_address_erc20_txs(address, limit=limit)

            # Log Etherscan API errors for debugging
            for label, resp in [("normal", normal), ("internal", internal), ("erc20", erc20)]:
                if resp and resp.get("status") == "0":
                    self.logger.warning(
                        f"Etherscan {label} API error for {address}: {resp.get('message', '')} — {resp.get('result', '')}"
                    )

            result = []
            # Normal transactions
            if normal and isinstance(normal.get("result"), list):
                for tx in normal["result"]:
                    result.append(self._normalize_tx(tx, "normal"))
            # Internal transactions
            if internal and isinstance(internal.get("result"), list):
                for tx in internal["result"]:
                    result.append(self._normalize_tx(tx, "internal"))
            # Token transfers
            if erc20 and isinstance(erc20.get("result"), list):
                for tx in erc20["result"]:
                    result.append(self._normalize_tx(tx, "erc20"))

            result.sort(key=lambda x: x.get("timeStamp", 0), reverse=True)
            return result[:limit]

        except Exception as e:
            self.logger.error(f"Error getting transactions for {address}: {e}")
            return []

    def _normalize_tx(self, tx: dict, tx_type: str) -> dict:
        """Normalize Etherscan response to unified format."""
        base = {
            "txid": tx.get("hash", ""),
            "from": tx.get("from", ""),
            "to": tx.get("to", ""),
            "value": int(tx.get("value", 0)),
            "timeStamp": int(tx.get("timeStamp", 0)),
            "blockNumber": int(tx.get("blockNumber", 0)),
            "gas": int(tx.get("gas", 0)),
            "gasPrice": int(tx.get("gasPrice", 0)),
            "gasUsed": int(tx.get("gasUsed", 0)),
            "isError": tx.get("isError", "0"),
            "tx_type": tx_type,
            "chain": "eth",
        }

        if tx_type == "erc20":
            base.update({
                "value": 0,  # ERC20 transfers don't move ETH
                "tokenSymbol": tx.get("tokenSymbol", ""),
                "tokenName": tx.get("tokenName", ""),
                "tokenDecimal": int(tx.get("tokenDecimal", 18)),
                "tokenValue": int(tx.get("value", 0)),
                "contractAddress": tx.get("contractAddress", ""),
            })

        return base
