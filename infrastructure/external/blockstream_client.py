"""
Blockstream API client with improved error handling and retry logic.
"""
from base_api_client import BaseAPIClient
import logging

logger = logging.getLogger(__name__)

class BlockstreamClient(BaseAPIClient):
    BASE = "https://blockstream.info/api"

    def __init__(self):
        super().__init__(
            base_url=self.BASE,
            timeout=15,
            max_retries=5,
            retry_delay=1.0,
            rate_limit_delay=0.5
        )

    def get_address_info(self, address):
        return self._get(f"/address/{address}")

    def get_address_txs(self, address, limit=200):
        import time as _time
        txs = []
        last_seen = None

        # Validar formato básico de dirección Bitcoin
        if not self._is_valid_btc_address(address):
            logger.warning("Invalid Bitcoin address format for transaction lookup: %s", address)
            return []

        while True:
            if last_seen:
                endpoint = f"/address/{address}/txs/chain/{last_seen}"
            else:
                endpoint = f"/address/{address}/txs/chain"

            try:
                batch = self._get(endpoint)
            except Exception as e:
                # Manejar específicamente errores 404 (no hay transacciones en cadena)
                if hasattr(e, 'status_code') and getattr(e, 'status_code', None) == 404:
                    logger.info("No chain transactions found for address %s", address)
                    break
                else:
                    # Re-lanzar otros errores
                    raise e

            if not batch:
                break

            txs.extend(batch)

            if len(batch) < 25:
                break

            last_seen = batch[-1]["txid"]

            if len(txs) >= limit:
                break

            # Throttle between pagination requests to avoid rate limits
            _time.sleep(self.rate_limit_delay)

        return txs[:limit]

    def _is_valid_btc_address(self, address):
        """
        Validación básica de formato de dirección Bitcoin.
        No es exhaustiva pero filtra claramente direcciones inválidas.
        """
        if not address or not isinstance(address, str):
            return False
        
        # Eliminar espacios en blanco
        address = address.strip()
        
        # Dirección vacía después de trim
        if not address:
            return False
            
        # Longitud típica de direcciones Bitcoin (26-62 caracteres)
        if len(address) < 26 or len(address) > 62:
            return False
            
        # Prefijos comunes de direcciones Bitcoin
        # Direcciones legacy (comienzan con 1)
        # Direcciones P2SH (comienzan con 3)
        # Direcciones Bech32 (comienzan con bc1)
        if address.startswith(('1', '3', 'bc1')):
            return True
            
        # Otros formatos menos comunes pero válidos
        if address.startswith(('m', 'n', '2', 'mb', 'nb')):  # Testnet
            return True
            
        return False

    def get_tx(self, txid):
        return self._get(f"/tx/{txid}")

    def get_tx_inputs(self, txid):
        return self._get(f"/tx/{txid}/ins") or []

    def get_tx_outputs(self, txid):
        return self._get(f"/tx/{txid}/outs") or []