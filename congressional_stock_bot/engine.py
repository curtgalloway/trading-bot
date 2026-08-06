from __future__ import annotations

from dataclasses import asdict
from typing import Iterable, List

from .brokers.base import BrokerAdapter
from .models import TradePlan, TradeSignal
from .risk import build_trade_plan


def plan_signals(
    signals: Iterable[TradeSignal],
    broker: BrokerAdapter,
    stop_loss_pct: float = 0.03,
    take_profit_pct: float = 0.05,
) -> List[TradePlan]:
    portfolio = broker.get_account_value_eur()
    plans: list[TradePlan] = []

    for signal in signals:
        quote = broker.get_quote(signal.symbol)
        plans.append(
            build_trade_plan(
                signal=signal,
                reference_price=quote,
                portfolio_eur=portfolio,
                stop_loss_pct=stop_loss_pct,
                take_profit_pct=take_profit_pct,
            )
        )

    return plans


def execute_plans(plans: Iterable[TradePlan], broker: BrokerAdapter, dry_run: bool = True) -> list[dict]:
    results: list[dict] = []

    for plan in plans:
        side = plan.signal.action
        if dry_run:
            results.append(
                {
                    "mode": "DRY_RUN",
                    "order": {
                        "symbol": plan.signal.symbol,
                        "side": side,
                        "quantity": plan.quantity,
                    },
                    "plan": asdict(plan),
                }
            )
        else:
            results.append(broker.place_market_order(plan.signal.symbol, side, plan.quantity))

    return results

