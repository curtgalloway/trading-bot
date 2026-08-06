from __future__ import annotations

from abc import ABC, abstractmethod


class BrokerAdapter(ABC):
    @abstractmethod
    def get_quote(self, symbol: str) -> float:
        raise NotImplementedError

    @abstractmethod
    def place_market_order(self, symbol: str, side: str, quantity: float) -> dict:
        raise NotImplementedError

    @abstractmethod
    def get_account_value_eur(self) -> float:
        raise NotImplementedError

