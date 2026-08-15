"""
Koios Adapter - Implements BlockchainAPI port for Cardano via Koios API.
"""
from typing import Optional, Dict, List, Any
import logging

from domain.ports.blockchain_api import BlockchainAPI
from infrastructure.external.koios_client import KoiosClient, _from_lovelaces, _sum_ada_from_value, _extract_assets_from_value

logger = logging.getLogger(__name__)


class KoiosAdapter(BlockchainAPI):
    """Adapter that makes KoiosClient conform to BlockchainAPI port for Cardano."""

    def __init__(self, koios_client: Optional[KoiosClient] = None):
        self.client = koios_client or KoiosClient()
        self.logger = logger

    def get_address_info(self, address: str, chain: str = "ada") -> Optional[Dict[str, Any]]:
        """Get Cardano address info from Koios."""
        try:
            self.logger.debug(f"Getting address info for {address} from Koios")
            info = self.client.get_address_info(address)
            if not info:
                return None

            # Koios returns list of addresses; we queried one
            balance_lovelaces = _sum_ada_from_value(info.get("balance", []))
            stake_address = info.get("stake_address")

            return {
                "address": address,
                "balance": _from_lovelaces(balance_lovelaces),
                "balance_lovelaces": balance_lovelaces,
                "stake_address": stake_address,
                "tx_count": info.get("tx_count", 0),
                "assets": _extract_assets_from_value(info.get("balance", [])),
                "chain": "ada",
            }
        except Exception as e:
            self.logger.error(f"Error getting address info for {address}: {e}")
            return None

    def get_transaction(self, txid: str, chain: str = "ada") -> Optional[Dict[str, Any]]:
        """Get transaction details from Koios."""
        try:
            self.logger.debug(f"Getting transaction {txid} from Koios")
            tx = self.client.get_transaction(txid)
            if not tx:
                return None

            # Normalize transaction format
            return {
                "txid": tx.get("tx_hash"),
                "block_height": tx.get("block_height"),
                "block_time": tx.get("block_time"),
                "epoch_no": tx.get("epoch_no"),
                "fees": _from_lovelaces(int(tx.get("fees", 0))),
                "inputs": tx.get("inputs", []),
                "outputs": tx.get("outputs", []),
                "metadata": tx.get("metadata"),
                "chain": "ada",
            }
        except Exception as e:
            self.logger.error(f"Error getting transaction {txid}: {e}")
            return None

    def get_transaction_inputs(self, txid: str, chain: str = "ada") -> List[Dict[str, Any]]:
        """Get transaction inputs (UTxOs consumed)."""
        try:
            tx = self.client.get_transaction(txid)
            if not tx:
                return []
            inputs = tx.get("inputs", [])
            # Normalize input format
            return [{
                "tx_hash": inp.get("tx_hash"),
                "output_index": inp.get("index"),
                "address": inp.get("address"),
                "amount": _from_lovelaces(_sum_ada_from_value(inp.get("value", []))),
                "amount_lovelaces": _sum_ada_from_value(inp.get("value", [])),
                "assets": _extract_assets_from_value(inp.get("value", [])),
            } for inp in inputs]
        except Exception as e:
            self.logger.error(f"Error getting transaction inputs for {txid}: {e}")
            return []

    def get_transaction_outputs(self, txid: str, chain: str = "ada") -> List[Dict[str, Any]]:
        """Get transaction outputs (UTxOs created)."""
        try:
            tx = self.client.get_transaction(txid)
            if not tx:
                return []
            outputs = tx.get("outputs", [])
            # Normalize output format
            return [{
                "address": out.get("address"),
                "amount": _from_lovelaces(_sum_ada_from_value(out.get("value", []))),
                "amount_lovelaces": _sum_ada_from_value(out.get("value", [])),
                "assets": _extract_assets_from_value(out.get("value", [])),
                "datum_hash": out.get("datum_hash"),
                "inline_datum": out.get("inline_datum"),
                "reference_script": out.get("reference_script"),
            } for out in outputs]
        except Exception as e:
            self.logger.error(f"Error getting transaction outputs for {txid}: {e}")
            return []

    def get_address_transactions(self, address: str, limit: int = 200,
                                 chain: str = "ada") -> List[Dict[str, Any]]:
        """Get transactions for a Cardano address from Koios with full details."""
        try:
            self.logger.debug(f"Getting transactions for {address} from Koios (limit: {limit})")
            txs = self.client.get_address_transactions(address, limit=limit)

            normalized = []
            for tx in txs:
                tx_hash = tx.get("tx_hash")
                if not tx_hash:
                    continue

                # Fetch full transaction details for inputs/outputs
                full_tx = self.client.get_transaction(tx_hash)
                if not full_tx:
                    self.logger.warning(f"Could not fetch full tx details for {tx_hash}")
                    continue

                # Get inputs and outputs
                inputs = full_tx.get("inputs", [])
                outputs = full_tx.get("outputs", [])

                # Determine direction and amount for this address
                sent_amount = 0
                received_amount = 0

                # Check inputs (sent from this address)
                for inp in inputs:
                    inp_addr = inp.get("address")
                    if inp_addr == address:
                        sent_amount += _sum_ada_from_value(inp.get("value", []))

                # Check outputs (received by this address)
                for out in outputs:
                    out_addr = out.get("address")
                    if out_addr == address:
                        received_amount += _sum_ada_from_value(out.get("value", []))

                # Normalize inputs
                norm_inputs = []
                for inp in inputs:
                    inp_value = inp.get("value", [])
                    norm_inputs.append({
                        "tx_hash": inp.get("tx_hash"),
                        "output_index": inp.get("index"),
                        "address": inp.get("address"),
                        "amount": _from_lovelaces(_sum_ada_from_value(inp_value)),
                        "amount_lovelaces": _sum_ada_from_value(inp_value),
                        "assets": _extract_assets_from_value(inp_value),
                    })

                # Normalize outputs
                norm_outputs = []
                for out in outputs:
                    out_value = out.get("value", [])
                    norm_outputs.append({
                        "address": out.get("address"),
                        "amount": _from_lovelaces(_sum_ada_from_value(out_value)),
                        "amount_lovelaces": _sum_ada_from_value(out_value),
                        "assets": _extract_assets_from_value(out_value),
                        "datum_hash": out.get("datum_hash"),
                        "inline_datum": out.get("inline_datum"),
                        "reference_script": out.get("reference_script"),
                    })

                normalized.append({
                    "txid": tx_hash,
                    "block_height": tx.get("block_height"),
                    "block_time": tx.get("block_time"),
                    "epoch_no": tx.get("epoch_no"),
                    "fees": _from_lovelaces(int(tx.get("fees", 0))),
                    "inputs": norm_inputs,
                    "outputs": norm_outputs,
                    "sent_amount": _from_lovelaces(sent_amount),
                    "received_amount": _from_lovelaces(received_amount),
                    "chain": "ada",
                })

            self.logger.info(f"Found {len(normalized)} transactions for {address}")
            return normalized
        except Exception as e:
            self.logger.error(f"Error getting address transactions for {address}: {e}")
            return []

    # --- Additional Cardano-specific methods ---

    def get_address_utxos(self, address: str) -> List[Dict[str, Any]]:
        """Get UTxOs for an address."""
        return self.client.get_address_utxos(address)

    def get_stake_account_addresses(self, stake_address: str) -> List[Dict[str, Any]]:
        """Get all payment addresses for a stake account."""
        return self.client.get_account_addresses(stake_address)

    def get_account_info(self, stake_address: str):
        """Get stake account info (delegation, rewards, etc.)."""
        return self.client.get_account_info(stake_address)