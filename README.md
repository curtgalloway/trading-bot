# Crypto Trading Monitor Bot

An automated cryptocurrency trading bot for Coinbase Advanced Trade API that implements profit-taking, stop-loss, and buy-the-dip strategies on BTC and ETH.

**Status**: Live Trading (Phase 5 — Nov 13, 2026)
**Budget**: €50 (~$305 USDC real balance on Coinbase)
**Minimum Balance**: €5.00
**Monitoring**: Every 15 minutes

---

## Current Strategy (Phase 5 — Nov 13, 2026)

### Profit-Taking (Two-Stage Exit)

| Trigger | Action |
|---------|--------|
| **+25% gain** | Sell 50% of position (lock in gains) |
| **+40% gain** | Sell remaining 50% (full exit) |

### Stop-Loss

| Trigger | Action |
|---------|--------|
| **-20% loss** | Sell 100% of position |

### Buy-the-Dip (Primary Entry)

- Compare current price vs **7-day rolling high**
- Buy **€10** when price drops **≥12%** below 7-day high
- Skips assets already held (no duplicate)
- 24-hour cooldown per asset

### Re-Entry Logic

- After a position is sold, tracked for 30 days
- Buys back if price drops **10–15% below sale price**

### Time-Fallback Guard

- If idle **30+ days** with no buys, attempts a fallback buy
- **Requires dip ≥10%** below 7-day high (no blind buys)

---

## Features

### Trading Strategies

- **Staged Profit Exit**: Sell 50% at +25%, remaining 50% at +40%
- **Stop-Loss Protection**: Full exit at -20% loss
- **Buy-the-Dip**: Buys BTC/ETH on meaningful pullbacks (≥12% from 7-day high)
- **Re-Entry Logic**: Re-buys sold positions on deeper dips (10-15% below sale price)
- **Time-Fallback Guard**: Prevents idle capital with dip-filtered buys

### Risk Management

- Real USDC balance tracking from Coinbase (not virtual budget)
- Minimum balance protection ($5.00 buffer)
- Position tracking with entry price and P&L
- 24-hour buy cooldown per asset
- Configurable trading fees (taker: 1.2%, maker: 0.6%)
- Dry-run mode for testing

### Monitoring

- 15-minute monitoring cycle
- Real-time portfolio tracking
- 7-day rolling price history for dip detection
- Sold position tracking (30-day expiry)
- Comprehensive file + console logging
- Currency conversion (EUR, USDC, USD, USDT)
- Automatic periodic analysis (every 7 days, recommends trigger changes)

---

## How It Works

The bot runs on a 15-minute cycle:

1. **Fetch Portfolio** — Check current holdings via Coinbase API
2. **Record Prices** — Track prices for dip detection
3. **Check Sell Triggers** — Compare profits/losses to thresholds
4. **Execute Sells** — Place market orders when targets hit
5. **Check Buy Triggers** — Look for dip-buying, re-entry, and fallback opportunities
6. **Execute Buys** — Place market orders for qualified signals
7. **Update Tracking** — Save position and price data
8. **Sleep** — Wait 15 minutes, repeat

---

## Project Structure

```
trading_monitor.py        # Main bot script (continuous monitoring loop)
coinbase_api.py           # Coinbase API wrapper + utilities
dip_signal_analyzer.py    # Market signals (funding rates, liquidations, fear/greed)
check_dip_signals.py      # Quick manual dip scan (keyword-based)
analyze_performance.py    # P&L analysis + missed opportunities
optimize_triggers.py      # Manual trigger optimizer + backtesting
backtest.py               # Historical backtesting
test_*.py                 # Test scripts
trading_config.json       # Trading config (editable, not in git)
cdp_api_key.json          # API credentials (not in git)
trading_monitor.log       # Runtime log
trading_analysis.log      # Periodic analysis recommendations
```

---

## Configuration

### trading_config.json

```json
{
  "trading_budget_eur": 50.0,
  "minimum_balance_eur": 5.0,
  "check_interval_minutes": 15,
  "dry_run": false,

  "triggers": {
    "profit_target_percent": 25,
    "profit_target_sell_percent": 50,
    "final_profit_target_percent": 40,
    "stop_loss_percent": 20,
    "buy_dip_percent": 12,
    "buy_assets": ["BTC", "ETH"],
    "buy_amount_eur": 10,
    "buy_cooldown_hours": 24
  },

  "fees": {
    "taker_fee_rate": 0.012,
    "maker_fee_rate": 0.006
  },

  "tracked_assets": ["BTC", "ETH"],

  "time_fallback": {
    "enabled": true,
    "max_idle_days": 30,
    "fallback_amount_eur": 10,
    "fallback_assets": ["BTC", "ETH"],
    "require_dip": true,
    "min_dip_percent": 10
  },

  "analysis": {
    "enabled": true,
    "frequency_days": 7,
    "min_positions_for_analysis": 5
  }
}
```

### How to Adjust

- **dry_run: true** — Test without real trades
- **stop_loss_percent** — Wider = fewer false stops, but larger max loss
- **profit_target_percent** — Higher = more upside but fewer hits
- **buy_dip_percent** — Higher = more selective entries
- **buy_assets** — Add/remove coins (BTC, ETH recommended for stability)

---

## API Reference

### CoinbaseAPI Class

```python
from coinbase_api import CoinbaseAPI

api = CoinbaseAPI('cdp_api_key.json')

# Get current price
price_data = api.get_price('BTC')  # {'price': 93000, 'currency': 'USDC', ...}

# Get account balances
accounts = api.get_accounts()
usdc_balance = api.get_balance('USDC')

# Place a market order
api.place_order('BTC-USDC', 'BUY', 10.0, 'quote_size')     # Buy $10 worth
api.place_order('BTC-USDC', 'SELL', 0.001, 'base_size')    # Sell 0.001 BTC
```

---

## Safety Features

- **Budget Protection**: Halts trading below minimum balance
- **Rate Limiting**: 10 requests/second max on Coinbase API
- **Retry Logic**: Automatic retries with exponential backoff
- **Precision Rounding**: Order sizes rounded to API requirements
- **Error Logging**: All errors logged to `trading_monitor.log`
- **Dry-Run Mode**: Strategy testing without real capital

---

## Logging

All activity logged to `trading_monitor.log`:
- Trade executions (buy/sell)
- Position tracking updates
- Trigger activations
- API errors and retries

Console output provides real-time monitoring.

Periodic analysis writes to `trading_analysis.log`:
- Portfolio P&L, win rate, max gain/loss
- Current vs. suggested trigger values
- Changes ≥2% are flagged for manual review

---

## Known Issues & Limitations

- **Insufficient funds**: Check real balance vs. tracked budget
- **Invalid order size**: Bot auto-rounds, but minimum order sizes apply
- **No buy triggers**: Need 7+ days of price history for dip detection
- **Tiny positions**: Very small holdings may fall below minimum order size
- **No auto-apply**: Analysis recommendations require manual config update

---

## Disclaimer

This bot is for educational purposes. Cryptocurrency trading carries significant risk:

- You can lose all invested capital
- Past performance does not guarantee future results
- Test thoroughly in dry-run mode before live trading
- Start with small amounts you can afford to lose
- Monitor the bot regularly — automation does not mean "set and forget"

**Use at your own risk. The authors take no responsibility for any financial losses.**

---

**Project Location**: `~/prog/trading-bot`
**Created**: February 2026
**Last Updated**: November 13, 2026 (Phase 5 triggers)
**Maintained By**: Curt Galloway
