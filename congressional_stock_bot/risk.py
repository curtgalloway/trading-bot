from __future__ import annotations

from math import floor

from .models import TradePlan, TradeSignal


def _action_multiplier(action: str) -> float:
    return 1.25 if action == "SELL" else 0.8


def _cluster_multiplier(cluster_size: int) -> float:
    if cluster_size >= 4:
        return 1.5
    if cluster_size == 3:
        return 1.25
    return 1.0


def recommended_notional_eur(signal: TradeSignal, portfolio_eur: float) -> float:
    base_risk = portfolio_eur * 0.02
    confidence = max(0.5, min(signal.confidence, 1.0))
    notional = base_risk * confidence * _action_multiplier(signal.action) * _cluster_multiplier(signal.cluster_size)
    return min(notional, portfolio_eur * 0.10)


def build_trade_plan(
    signal: TradeSignal,
    reference_price: float,
    portfolio_eur: float,
    stop_loss_pct: float = 0.03,
    take_profit_pct: float = 0.05,
) -> TradePlan:
    if reference_price <= 0:
        raise ValueError("reference_price must be positive")

    notional = recommended_notional_eur(signal, portfolio_eur)
    # IBKR's fractional-share increment for US equities is 0.0001 shares.
    quantity = floor((notional / reference_price) * 10000) / 10000
    if quantity <= 0:
        raise ValueError("Calculated trade quantity is zero")

    return TradePlan(
        signal=signal,
        reference_price=reference_price,
        quantity=quantity,
        notional_eur=quantity * reference_price,
        max_risk_eur=portfolio_eur * 0.02,
        stop_loss_pct=stop_loss_pct,
        take_profit_pct=take_profit_pct,
        position_fraction=(quantity * reference_price) / portfolio_eur,
    )

