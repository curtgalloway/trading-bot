from dataclasses import dataclass, field
from typing import Any, Dict, Literal

Action = Literal["BUY", "SELL"]


@dataclass(frozen=True)
class TradeSignal:
    symbol: str
    action: Action
    confidence: float
    cluster_size: int
    source: str = "congressional-trades"
    source_date: str = ""
    horizon_days: int = 30
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TradePlan:
    signal: TradeSignal
    reference_price: float
    quantity: float
    notional_eur: float
    max_risk_eur: float
    stop_loss_pct: float
    take_profit_pct: float
    position_fraction: float

