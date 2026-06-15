"""
TRONGRID API client for TRON (TRX) blockchain.
Public API at https://api.trongrid.io, no API key required.
"""
from base_api_client import BaseAPIClient
import logging

logger = logging.getLogger(__name__)


class TronGridClient(BaseAPIClient):
    BASE = "https://api.trongrid.io"

    def __init__(self):
        super().__init__(
            base_url=self.BASE,
            timeout=15,
            max_retries=5,
            retry_delay=1.0,
            rate_limit_delay=0.3,
        )

    def get_account_info(self, address: str):
        return self._get(f"/v1/accounts/{address}")

    def get_account_transactions(self, address: str, limit: int = 200):
        import time as _time
        txs = []
        next_token = None

        while True:
            params = {"limit": min(limit, 200), "only_to": False, "only_confirmed": True}
            if next_token:
                params["fingerprint"] = next_token

            resp = self._get(f"/v1/accounts/{address}/transactions", params=params)
            if not resp:
                break

            batch = resp.get("data", [])
            if not batch:
                break

            txs.extend(batch)
            meta = resp.get("meta", {})
            next_token = meta.get("fingerprint")

            if not next_token or len(txs) >= limit:
                break
            _time.sleep(self.rate_limit_delay)

        return txs[:limit]

    def get_account_trc20(self, address: str, limit: int = 200):
        import time as _time
        txs = []
        next_token = None

        while True:
            params = {"limit": min(limit, 200), "only_confirmed": True}
            if next_token:
                params["fingerprint"] = next_token

            resp = self._get(f"/v1/accounts/{address}/transactions/trc20", params=params)
            if not resp:
                break

            batch = resp.get("data", [])
            if not batch:
                break

            txs.extend(batch)
            meta = resp.get("meta", {})
            next_token = meta.get("fingerprint")

            if not next_token or len(txs) >= limit:
                break
            _time.sleep(self.rate_limit_delay)

        return txs[:limit]

    def get_transaction(self, txid: str):
        return self._get(f"/v1/transactions/{txid}")
