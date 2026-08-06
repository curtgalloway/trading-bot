#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from congressional_stock_bot.brokers import DryRunBroker, IBKRBroker
from congressional_stock_bot.engine import execute_plans, plan_signals
from congressional_stock_bot.signal_loader import load_signals


def main() -> int:
    parser = argparse.ArgumentParser(description="Congressional stock signal runner")
    parser.add_argument("--signals", default="congressional_signals.json", help="Signal file path")
    parser.add_argument("--quotes-file", default="", help="Optional JSON map of symbol to price")
    parser.add_argument("--portfolio", type=float, default=50000.0, help="Portfolio value in EUR")
    parser.add_argument("--execute", action="store_true", help="Place orders instead of simulating")
    parser.add_argument("--broker", choices=["dry-run", "ibkr"], default="dry-run", help="Broker adapter")
    parser.add_argument("--ibkr-base-url", default=os.environ.get("IBKR_BASE_URL", "https://localhost:5000/v1/api"))
    parser.add_argument("--ibkr-account-id", default=os.environ.get("IBKR_ACCOUNT_ID", ""))
    parser.add_argument("--ibkr-verify-ssl", action="store_true", help="Verify IBKR gateway SSL cert")
    args = parser.parse_args()

    signals_path = Path(args.signals)
    if not signals_path.exists():
        raise FileNotFoundError(f"Signal file not found: {signals_path}")

    signals = load_signals(signals_path)
    quotes = {}
    if args.quotes_file:
        quotes = json.loads(Path(args.quotes_file).read_text(encoding="utf-8"))
    dry_run = not args.execute
    if args.broker == "ibkr":
        broker = IBKRBroker(
            base_url=args.ibkr_base_url,
            account_id=args.ibkr_account_id or None,
            verify_ssl=args.ibkr_verify_ssl,
            fallback_quotes=quotes,
            portfolio_value_eur=args.portfolio,
        )
    else:
        broker = DryRunBroker(portfolio_value_eur=args.portfolio, quotes=quotes)

    if args.broker == "ibkr":
        for signal in signals:
            ref = signal.metadata.get("reference_price")
            if ref is not None and signal.symbol not in quotes:
                quotes[signal.symbol] = float(ref)

    print(f"Loaded {len(signals)} congressional signal(s)")
    print(f"Dry-run mode: {'ON' if dry_run else 'OFF'}")
    print()

    enriched = []
    for signal in signals:
        if args.broker == "ibkr":
            enriched.append(signal)
            continue
        if signal.symbol in broker.quotes:
            enriched.append(signal)
            continue
        reference_price = signal.metadata.get("reference_price")
        if reference_price:
            broker.quotes[signal.symbol] = float(reference_price)
            enriched.append(signal)

    if not enriched:
        print("No usable quotes found.")
        print("Add a quotes file or include metadata.reference_price in each signal.")
        return 1

    plans = plan_signals(enriched, broker)
    results = execute_plans(plans, broker, dry_run=dry_run)

    for result in results:
        print(json.dumps(result, indent=2))

    print()
    print(f"Broker: {args.broker}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
