"""
Blockfrost Adapter - Implements BlockchainAPI port for Cardano via Blockfrost API.
"""
from typing import Optional, Dict, List, Any
import logging

from domain.ports.blockchain_api import BlockchainAPI
from infrastructure.external.blockfrost_client import (
    BlockfrostClient, _from_lovelaces, _sum_ada_from_amount,
    _extract_assets_from_amount, _decode_asset_name_hex,
)

logger = logging.getLogger(__name__)


class BlockfrostAdapter(BlockchainAPI):
    """Adapter that makes BlockfrostClient conform to BlockchainAPI port for Cardano."""

    def __init__(self, config: Optional[object] = None, blockfrost_client: Optional[BlockfrostClient] = None):
        self.config = config
        self.client = blockfrost_client
        self.logger = logger

    def _ensure_client(self) -> Optional[BlockfrostClient]:
        """Ensure client is initialized with API key."""
        if self.client is None:
            api_key = None
            # Try config first
            if self.config and hasattr(self.config, 'api') and hasattr(self.config.api, 'blockfrost_api_key'):
                api_key = self.config.api.blockfrost_api_key
            # Fallback to environment
            if not api_key:
                import os
                api_key = os.environ.get("BLOCKFROST_API_KEY")
            if not api_key:
                logger.error("BLOCKFROST_API_KEY not set in environment or config")
                return None
            self.client = BlockfrostClient(project_id=api_key)
        return self.client

    def get_address_info(self, address: str, chain: str = "ada") -> Optional[Dict[str, Any]]:
        """Get Cardano address info from Blockfrost."""
        client = self._ensure_client()
        if not client:
            return None
        try:
            self.logger.debug(f"Getting address info for {address} from Blockfrost")
            info = client.get_address_info(address)
            if not info:
                return None

            return {
                "address": address,
                "balance": info.get("balance_ada", 0),
                "balance_lovelaces": info.get("balance_lovelaces", 0),
                "stake_address": info.get("stake_address"),
                "tx_count": info.get("tx_count", 0),
                "received_sum": _from_lovelaces(info.get("received_sum", 0)),
                "sent_sum": _from_lovelaces(info.get("sent_sum", 0)),
                "chain": "ada",
            }
        except Exception as e:
            self.logger.error(f"Error getting address info for {address}: {e}")
            return None

    def get_address_tokens(self, address: str, chain: str = "ada") -> List[Dict[str, Any]]:
        """List native tokens currently held by a Cardano address, with
        on-chain metadata resolved (ticker/name/decimals) where available.

        This mirrors what block explorers show under an address's "Tokens"
        tab: it reads live UTxO holdings rather than requiring a
        hand-maintained policy_id list, and surfaces the real policy_id
        next to each resolved name so two tokens sharing a ticker (e.g. a
        legitimate "USD" token vs. an impersonation minted under a
        different policy_id) can be told apart.
        """
        client = self._ensure_client()
        if not client:
            return []
        try:
            details = client.get_address_details(address)
            if not details:
                return []

            tokens = []
            for item in details.get("amount", []):
                unit = item.get("unit", "")
                if unit == "lovelace" or not unit:
                    continue

                policy_id = unit[:56] if len(unit) >= 56 else ""
                asset_name_hex = unit[56:] if len(unit) > 56 else ""
                display_name = _decode_asset_name_hex(asset_name_hex) if asset_name_hex else ""
                ticker = None
                decimals = 0

                info = client.get_asset_info(unit)
                if info:
                    registry_meta = info.get("metadata") or {}
                    onchain_meta = info.get("onchain_metadata") or {}
                    ticker = registry_meta.get("ticker") or onchain_meta.get("ticker")
                    decimals = registry_meta.get("decimals", 0) or 0
                    display_name = (
                        registry_meta.get("name") or onchain_meta.get("name") or display_name
                    )

                raw_quantity = int(item.get("quantity", 0))
                tokens.append({
                    "unit": unit,
                    "policy_id": policy_id,
                    "asset_name_hex": asset_name_hex,
                    "display_name": display_name or asset_name_hex or "(sin nombre)",
                    "ticker": ticker,
                    "decimals": decimals,
                    "quantity_raw": raw_quantity,
                    "quantity": raw_quantity / (10 ** decimals) if decimals else raw_quantity,
                })

            return tokens
        except Exception as e:
            self.logger.error(f"Error getting tokens for {address}: {e}")
            return []

    def get_transaction(self, txid: str, chain: str = "ada") -> Optional[Dict[str, Any]]:
        """Get transaction details from Blockfrost."""
        client = self._ensure_client()
        if not client:
            return None
        try:
            self.logger.debug(f"Getting transaction {txid} from Blockfrost")
            tx = client.get_transaction(txid)
            if not tx:
                return None

            utxos = client.get_transaction_utxos(txid)
            inputs = []
            outputs = []
            if utxos:
                for inp in utxos.get("inputs", []):
                    inputs.append({
                        "tx_hash": inp.get("tx_hash"),
                        "output_index": inp.get("output_index"),
                        "address": inp.get("address"),
                        "amount": _from_lovelaces(_sum_ada_from_amount(inp.get("amount", []))),
                        "assets": _extract_assets_from_amount(inp.get("amount", [])),
                    })
                for out in utxos.get("outputs", []):
                    outputs.append({
                        "address": out.get("address"),
                        "amount": _from_lovelaces(_sum_ada_from_amount(out.get("amount", []))),
                        "assets": _extract_assets_from_amount(out.get("amount", [])),
                        "datum_hash": out.get("datum_hash"),
                        "inline_datum": out.get("inline_datum"),
                        "reference_script": out.get("reference_script"),
                    })

            return {
                "txid": tx.get("tx_hash"),
                "block_height": tx.get("block_height"),
                "block_time": tx.get("block_time"),
                "epoch_no": tx.get("epoch_no"),
                "fees": _from_lovelaces(int(tx.get("fees", 0))),
                "inputs": inputs,
                "outputs": outputs,
                "metadata": tx.get("metadata"),
                "chain": "ada",
            }
        except Exception as e:
            self.logger.error(f"Error getting transaction {txid}: {e}")
            return None

    def get_transaction_inputs(self, txid: str, chain: str = "ada") -> List[Dict[str, Any]]:
        """Get transaction inputs (UTxOs consumed)."""
        client = self._ensure_client()
        if not client:
            return []
        try:
            utxos = client.get_transaction_utxos(txid)
            if not utxos:
                return []
            inputs = []
            for inp in utxos.get("inputs", []):
                amount_list = inp.get("amount", [])
                inputs.append({
                    "tx_hash": inp.get("tx_hash"),
                    "output_index": inp.get("output_index"),
                    "address": inp.get("address"),
                    "amount": _from_lovelaces(_sum_ada_from_amount(amount_list)),
                    "amount_lovelaces": _sum_ada_from_amount(amount_list),
                    "assets": _extract_assets_from_amount(amount_list),
                })
            return inputs
        except Exception as e:
            self.logger.error(f"Error getting transaction inputs for {txid}: {e}")
            return []

    def get_transaction_outputs(self, txid: str, chain: str = "ada") -> List[Dict[str, Any]]:
        """Get transaction outputs (UTxOs created)."""
        client = self._ensure_client()
        if not client:
            return []
        try:
            utxos = client.get_transaction_utxos(txid)
            if not utxos:
                return []
            outputs = []
            for out in utxos.get("outputs", []):
                amount_list = out.get("amount", [])
                outputs.append({
                    "address": out.get("address"),
                    "amount": _from_lovelaces(_sum_ada_from_amount(amount_list)),
                    "amount_lovelaces": _sum_ada_from_amount(amount_list),
                    "assets": _extract_assets_from_amount(amount_list),
                    "datum_hash": out.get("datum_hash"),
                    "inline_datum": out.get("inline_datum"),
                    "reference_script": out.get("reference_script"),
                })
            return outputs
        except Exception as e:
            self.logger.error(f"Error getting transaction outputs for {txid}: {e}")
            return []

    def get_address_transactions(self, address: str, limit: int = 200,
                                 chain: str = "ada") -> List[Dict[str, Any]]:
        """Get transactions for a Cardano address from Blockfrost with full details."""
        client = self._ensure_client()
        if not client:
            return []
        try:
            self.logger.debug(f"Getting transactions for {address} from Blockfrost (limit: {limit})")

            # Get transactions (paginated)
            all_txs = []
            page = 1
            while len(all_txs) < limit:
                txs = client.get_address_transactions(address, limit=min(100, limit - len(all_txs)), page=page)
                if not txs:
                    break
                all_txs.extend(txs)
                if len(txs) < 100:
                    break
                page += 1
                if len(all_txs) >= limit:
                    break

            if not all_txs:
                return []

            normalized = []
            for tx in all_txs[:limit]:
                if not isinstance(tx, dict):
                    continue
                tx_hash = tx.get("tx_hash")
                if not tx_hash:
                    continue

                # Fetch full transaction details
                full_tx = self.client.get_transaction(tx_hash) if hasattr(self, 'client') else None
                # Use our client's get_transaction
                client = self._ensure_client()
                if not client:
                    continue
                full_tx = client.get_transaction(tx_hash)
                if not full_tx or not isinstance(full_tx, dict):
                    self.logger.warning(f"Could not fetch full tx details for {tx_hash}")
                    continue

                # Get UTxOs for inputs/outputs
                utxos = client.get_transaction_utxos(tx_hash)
                if not utxos:
                    continue

                inputs = utxos.get("inputs", [])
                outputs = utxos.get("outputs", [])

                sent_amount = 0
                received_amount = 0

                for inp in inputs:
                    inp_addr = inp.get("address")
                    if inp_addr == address:
                        sent_amount += _sum_ada_from_amount(inp.get("amount", []))

                for out in outputs:
                    out_addr = out.get("address")
                    if out_addr == address:
                        received_amount += _sum_ada_from_amount(out.get("amount", []))

                norm_inputs = []
                for inp in inputs:
                    amount_list = inp.get("amount", [])
                    norm_inputs.append({
                        "tx_hash": inp.get("tx_hash"),
                        "output_index": inp.get("output_index"),
                        "address": inp.get("address"),
                        "amount": _from_lovelaces(_sum_ada_from_amount(inp.get("amount", []))),
                        "amount_lovelaces": _sum_ada_from_amount(amount_list),
                        "assets": _extract_assets_from_amount(inp.get("amount", [])),
                    })

                norm_outputs = []
                for out in outputs:
                    amount_list = out.get("amount", [])
                    norm_outputs.append({
                        "address": out.get("address"),
                        "amount": _from_lovelaces(_sum_ada_from_amount(amount_list)),
                        "amount_lovelaces": _sum_ada_from_amount(amount_list),
                        "assets": _extract_assets_from_amount(amount_list),
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

            return normalized
        except Exception as e:
            self.logger.error(f"Error getting address transactions for {address}: {e}")
            return []

    def get_address_utxos(self, address: str) -> List[Dict[str, Any]]:
        """Get UTxOs for an address."""
        client = self._ensure_client()
        if not client:
            return []
        return client.get_address_utxos(address)

    def get_stake_account_addresses(self, stake_address: str) -> List[Dict[str, Any]]:
        """Get all payment addresses for a stake account."""
        client = self._ensure_client()
        if not client:
            return []
        return client.get_account_addresses(stake_address)

    def get_account_info(self, stake_address: str):
        """Get stake account info (delegation, rewards, etc.)."""
        client = self._ensure_client()
        if not client:
            return None
        return client.get_account_info(stake_address)