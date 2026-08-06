from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .base import BrokerAdapter


@dataclass
class DryRunBroker(BrokerAdapter):
    portfolio_value_eur: float = 0.0
    quotes: dict[str, float] = field(default_factory=dict)
    orders: List[dict] = field(default_factory=list)

    def get_quote(self, symbol: str) -> float:
        if symbol not in self.quotes:
            raise ValueError(f"No dry-run quote available for {symbol}")
        return float(self.quotes[symbol])

    def place_market_order(self, symbol: str, side: str, quantity: float) -> dict:
        order = {"symbol": symbol, "side": side, "quantity": quantity, "status": "SIMULATED"}
        self.orders.append(order)
        return order

    def get_account_value_eur(self) -> float:
        return self.portfolio_value_eur

