# walletexplorer_client.py
import logging
from base_api_client import BaseAPIClient

logger = logging.getLogger(__name__)

class WalletExplorerClient:
    BASE = "https://www.walletexplorer.com/api/1"

    def __init__(self):
        # Use BaseAPIClient for HTTP requests with retry and error handling
        self.api_client = BaseAPIClient(
            base_url=self.BASE,
            timeout=10,
            max_retries=3,
            retry_delay=0.5,
            rate_limit_delay=0.1
        )
        # Cache for processed data (address -> wallet_id, etc.)
        self.cache_wallet_id = {}
        self.cache_wallet_info = {}
        self.cache_wallet_addresses = {}

    # ---------------------------------------------------------
    # Obtener wallet_id (cluster)
    # ---------------------------------------------------------
    def get_wallet_id(self, address):
        if address in self.cache_wallet_id:
            return self.cache_wallet_id[address]

        # Validar formato básico de dirección Bitcoin
        if not self._is_valid_btc_address(address):
            logger.warning("Invalid Bitcoin address format: %s", address)
            self.cache_wallet_id[address] = "unknown"
            return "unknown"

        url = f"/address-lookup?address={address}"
        try:
            data = self.api_client._get(url)
            if data is None:
                logger.warning("No data returned for address-lookup: %s", address)
                self.cache_wallet_id[address] = "unknown"
                return "unknown"

            wid = data.get("wallet_id", "unknown")
            self.cache_wallet_id[address] = wid
            logger.debug("Cached wallet_id for %s: %s", address, wid)
            return wid
        except Exception as e:
            # Manejar específicamente errores 404 (dirección no encontrada/no tiene wallet)
            if hasattr(e, 'status_code') and getattr(e, 'status_code', None) == 404:
                logger.info("Address %s not found in WalletExplorer (no wallet cluster)", address)
                self.cache_wallet_id[address] = "unknown"
                return "unknown"
            else:
                logger.error("Error fetching wallet_id for %s: %s", address, e)
                self.cache_wallet_id[address] = "unknown"
                return "unknown"

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
            
        # Longitud mínima razonable para direcciones Bitcoin
        if len(address) < 26:
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

    # ---------------------------------------------------------
    # Obtener información del wallet (etiquetas, tags, etc.)
    # ---------------------------------------------------------
    def get_wallet_info(self, wallet_id):
        if wallet_id in self.cache_wallet_info:
            return self.cache_wallet_info[wallet_id]

        url = f"/wallet?wallet={wallet_id}&from=0&count=1"
        try:
            data = self.api_client._get(url)
            if data is None:
                logger.warning("No data returned for wallet: %s", wallet_id)
                self.cache_wallet_info[wallet_id] = None
                return None

            self.cache_wallet_info[wallet_id] = data
            logger.debug("Cached wallet_info for %s", wallet_id)
            return data
        except Exception as e:
            logger.error("Error fetching wallet_info for %s: %s", wallet_id, e)
            self.cache_wallet_info[wallet_id] = None
            return None

    # ---------------------------------------------------------
    # Obtener direcciones del cluster
    # ---------------------------------------------------------
    def get_wallet_addresses(self, wallet_id, limit=2000):
        if wallet_id in self.cache_wallet_addresses:
            return self.cache_wallet_addresses[wallet_id]

        url = f"/wallet-addresses?wallet={wallet_id}&limit={limit}"
        try:
            data = self.api_client._get(url)
            if data is None:
                logger.warning("No data returned for wallet-addresses: %s", wallet_id)
                self.cache_wallet_addresses[wallet_id] = []
                return []

            addrs = data.get("addresses", [])
            self.cache_wallet_addresses[wallet_id] = addrs
            logger.debug("Cached %d addresses for wallet %s", len(addrs), wallet_id)
            return addrs
        except Exception as e:
            logger.error("Error fetching wallet_addresses for %s: %s", wallet_id, e)
            self.cache_wallet_addresses[wallet_id] = []
            return []