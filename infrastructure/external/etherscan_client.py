"""
Etherscan API V2 client — multi-chain via chainid parameter.
Base URL: https://api.etherscan.io/v2/api
"""
import logging
from base_api_client import BaseAPIClient

logger = logging.getLogger(__name__)


class EtherscanClient(BaseAPIClient):
    BASE = "https://api.etherscan.io/v2/api"

    def __init__(self, api_key: str = ""):
        super().__init__(
            base_url=self.BASE,
            timeout=15,
            max_retries=5,
            retry_delay=1.0,
            rate_limit_delay=0.3,
        )
        self.api_key = api_key

    def _call(self, params: dict) -> dict:
        params["apikey"] = self.api_key
        return self._get("", params=params)

    def get_address_txs(self, address, chainid=1, limit=200):
        return self._call({
            "chainid": chainid, "action": "txlist",
            "address": address, "sort": "desc", "offset": 0, "limit": limit,
        })

    def get_address_internal_txs(self, address, chainid=1, limit=200):
        return self._call({
            "chainid": chainid, "action": "txlistinternal",
            "address": address, "sort": "desc", "offset": 0, "limit": limit,
        })

    def get_address_erc20_txs(self, address, chainid=1, limit=200):
        return self._call({
            "chainid": chainid, "action": "tokentx",
            "address": address, "sort": "desc", "offset": 0, "limit": limit,
        })

    def get_balance(self, address, chainid=1):
        return self._call({
            "chainid": chainid, "action": "balance", "address": address,
        })

    def get_token_balances(self, address, chainid=1):
        return self._call({
            "chainid": chainid, "action": "addresstokenbalance",
            "address": address,
        })
