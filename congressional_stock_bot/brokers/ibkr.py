from __future__ import annotations

import json
import ssl
import time
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .base import BrokerAdapter


def _first_float(*values: Any) -> Optional[float]:
    for value in values:
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


@dataclass
class IBKRBroker(BrokerAdapter):
    """
    IBKR Client Portal Gateway adapter.

    Requires the local gateway or Client Portal API to be running, usually at:
    https://localhost:5000/v1/api
    """

    base_url: str = "https://localhost:5000/v1/api"
    account_id: Optional[str] = None
    verify_ssl: bool = False
    symbol_to_conid: dict[str, int] = field(default_factory=dict)
    fallback_quotes: dict[str, float] = field(default_factory=dict)
    portfolio_value_eur: float = 0.0

    def __post_init__(self) -> None:
        self._ssl_context = None if self.verify_ssl else ssl._create_unverified_context()

    def _request(self, path: str, method: str = "GET", data: Optional[dict] = None) -> Any:
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        headers = {"Content-Type": "application/json"}
        body = None if data is None else json.dumps(data).encode("utf-8")
        req = Request(url, data=body, headers=headers, method=method)
        with urlopen(req, context=self._ssl_context, timeout=30) as response:
            payload = response.read().decode("utf-8")
            return json.loads(payload) if payload else {}

    def _resolve_conid(self, symbol: str) -> int:
        if symbol in self.symbol_to_conid:
            return self.symbol_to_conid[symbol]

        query = urlencode({"symbol": symbol, "name": "false"})
        result = self._request(f"iserver/secdef/search?{query}")
        if not result:
            raise ValueError(f"IBKR could not resolve symbol: {symbol}")

        if isinstance(result, list):
            match = result[0]
        elif isinstance(result, dict) and "contracts" in result and result["contracts"]:
            match = result["contracts"][0]
        else:
            match = result

        conid = match.get("conid") or match.get("contractId")
        if conid is None:
            raise ValueError(f"IBKR search response missing conid for symbol: {symbol}")

        conid = int(conid)
        self.symbol_to_conid[symbol] = conid
        return conid

    def get_quote(self, symbol: str) -> float:
        if symbol in self.fallback_quotes:
            return float(self.fallback_quotes[symbol])

        conid = self._resolve_conid(symbol)

        # IBKR's snapshot endpoint primes the market data subscription on the
        # first call and often only returns the conid with no price fields.
        # Poll a few times, with a short delay, until real fields show up.
        price = None
        for attempt in range(5):
            result = self._request(f"iserver/marketdata/snapshot?conids={conid}&fields=31,84,85,86")
            if isinstance(result, list) and result:
                quote = result[0]
            elif isinstance(result, dict):
                quote = result
            else:
                quote = {}

            price = _first_float(
                quote.get("31"),      # last
                quote.get("last"),
                quote.get("84"),      # close
                quote.get("86"),      # bid
                quote.get("85"),      # ask
                quote.get("lastPrice"),
            )
            if price is not None:
                break
            time.sleep(0.5)

        if price is None:
            raise ValueError(f"IBKR snapshot missing price for {symbol}")
        return price

    def get_account_value_eur(self) -> float:
        if self.portfolio_value_eur > 0:
            return float(self.portfolio_value_eur)

        if not self.account_id:
            accounts = self._request("portfolio/accounts")
            if isinstance(accounts, list) and accounts:
                self.account_id = accounts[0].get("accountId")

        if not self.account_id:
            raise ValueError("IBKR account_id is required to fetch account value")

        summary = self._request(f"portfolio/{self.account_id}/summary")
        for key in ("netliquidation", "netLiquidation", "netLiquidationValue"):
            entry = summary.get(key)
            if isinstance(entry, dict):
                value = _first_float(entry.get("amount"))
            else:
                value = _first_float(entry)
            if value is not None:
                return value
        raise RuntimeError("IBKR account value could not be determined")

    def place_market_order(self, symbol: str, side: str, quantity: float) -> dict:
        if not self.account_id:
            raise ValueError("IBKR account_id is required for live orders")

        conid = self._resolve_conid(symbol)
        order = {
            "conid": conid,
            "orderType": "MKT",
            "side": side.upper(),
            "quantity": quantity,
            "tif": "DAY",
            "outsideRth": False,
        }
        return self._request(
            f"iserver/account/{self.account_id}/orders",
            method="POST",
            data={"orders": [order]},
        )
