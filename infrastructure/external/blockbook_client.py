"""
Blockbook API client (BCH and other UTXO chains).
Blockbook is used by Trezor and other block explorers.
"""
from base_api_client import BaseAPIClient
import logging

logger = logging.getLogger(__name__)


class BlockbookClient(BaseAPIClient):
    BASE = "https://bchblockexplorer.com/api/v2"

    def __init__(self):
        super().__init__(
            base_url=self.BASE,
            timeout=15,
            max_retries=5,
            retry_delay=1.0,
            rate_limit_delay=0.5,
        )

    def get_address_info(self, address):
        return self._get(f"/address/{address}")

    def get_address_txs(self, address, limit=200):
        import time as _time
        txs = []
        page = 1

        while True:
            resp = self._get(f"/address/{address}?page={page}")
            if not resp:
                break

            txids = resp.get("txids", [])
            total_pages = resp.get("totalPages", 1)

            for txid in txids:
                tx = self._get(f"/tx/{txid}")
                if tx:
                    txs.append(tx)
                _time.sleep(self.rate_limit_delay)
                if len(txs) >= limit:
                    return txs[:limit]

            if page >= total_pages or len(txids) < 1000:
                break
            page += 1
            _time.sleep(self.rate_limit_delay)

        return txs[:limit]

    def get_tx(self, txid):
        return self._get(f"/tx/{txid}")

    def get_tx_inputs(self, txid):
        tx = self._get(f"/tx/{txid}")
        if tx:
            return tx.get("vin", [])
        return []

    def get_tx_outputs(self, txid):
        tx = self._get(f"/tx/{txid}")
        if tx:
            return tx.get("vout", [])
        return []
