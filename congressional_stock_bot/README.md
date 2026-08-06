# Congressional Stock Bot Scaffold

This package is the stock-trading sidecar for the crypto bot.

## What it does
- Loads congressional trade signals from JSON
- Sizes positions using a conservative risk model
- Plans trades against a broker quote feed
- Supports dry-run execution now
- Leaves the broker adapter open for Interactive Brokers later

## Layout
- `models.py` - signal and trade plan data structures
- `signal_loader.py` - reads signals from file
- `risk.py` - sizing and plan creation
- `engine.py` - plan and execute pipeline
- `brokers/dry_run.py` - simulation broker
- `brokers/base.py` - broker interface

## Next step
Add an `ibkr.py` broker adapter when you are ready to wire real execution.

## Running
- Dry run: `python3 run_congressional_bot.py --signals congressional_signals.example.json`
- IBKR dry planning: `python3 run_congressional_bot.py --broker ibkr --signals congressional_signals.json`
- Live execution: add `--execute` plus a running IBKR Client Portal Gateway

## IBKR prerequisites
- Client Portal Gateway running locally
- `IBKR_BASE_URL` and `IBKR_ACCOUNT_ID` set if not using defaults
- SSL verification disabled by default for local gateway; enable with `--ibkr-verify-ssl`
