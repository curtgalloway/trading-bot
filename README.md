# Crypto Trading Monitor Bot

An automated cryptocurrency trading bot for Coinbase Advanced Trade API. It monitors your portfolio, tracks price history, and executes trades based on configurable triggers for profit-taking, stop-loss, and buy-the-dip strategies.

## How It Works

The bot runs a continuous monitoring cycle (configurable interval, default 15 minutes):

1. **Check Holdings** — Fetch current portfolio from Coinbase API
2. **Track Prices** — Record prices for buy-the-dip detection (7-day rolling window)
3. **Check Sell Triggers** — For each held position, compare P&L against thresholds
4. **Execute Sells** — Place market sell orders when triggers activate
5. **Check Buy Triggers** — Look for dip-buying, re-entry, and fallback opportunities
6. **Execute Buys** — Place market buy orders for qualified signals
7. **Update Tracking** — Persist position and price data to `trading_config.json`
8. **Sleep** — Wait for next cycle

### Strategy Components

The bot supports several independent trading mechanisms, all configured in `trading_config.json`:

#### Profit-Taking (Staged Exit)
Sell a percentage of a position when it reaches a profit target. A second (final) target can be configured for full exit of the remainder. Partial sells are tracked so the bot knows how much is still open.

#### Stop-Loss
Automatically sells 100% of a position when losses reach a configured threshold. This is the primary downside protection.

#### Buy-the-Dip
Compares the current price against a rolling price history window (default 7 days). When the price drops below a configured percentage from the high, a buy order is triggered. The bot won't buy an asset you already hold (prevents duplicates).

#### Re-Entry Logic
When a position is fully sold, the bot remembers the sale price for a configurable window (default 30 days). If the price drops below a configured threshold from the sale price, it re-enters the position. This captures mean-reversion trades.

#### Time-Fallback Guard
If the bot hasn't bought anything for a configured number of days, it can trigger a fallback buy to keep capital deployed. This can be configured to require a dip (only buy if price is already below the 7-day high).

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/curtgalloway/trading-bot.git
   cd trading-bot
   ```

2. Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install PyJWT
   ```

4. Set up your Coinbase API credentials:
   - Create a CDP API key from [Coinbase Developer Portal](https://docs.cloud.coinbase.com/)
   - Save the credentials to `cdp_api_key.json` in the project directory

5. Configure your trading parameters in `trading_config.json`

## Configuration

All settings live in `trading_config.json`. The bot validates the config on startup.

### Core Settings

| Field | Type | Description |
|-------|------|-------------|
| `trading_budget_eur` | float | Total budget to trade with |
| `minimum_balance_eur` | float | Minimum buffer — halts trading if balance falls below this |
| `check_interval_minutes` | int | How often to run the monitoring cycle |
| `dry_run` | bool | `true` to simulate without real trades |

### Triggers

| Field | Type | Description |
|-------|------|-------------|
| `profit_target_percent` | float | Profit % to trigger first sell leg |
| `profit_target_sell_percent` | float | % of position to sell at profit target |
| `final_profit_target_percent` | float | Profit % for full position exit |
| `stop_loss_percent` | float | Loss % that triggers full exit |
| `buy_dip_percent` | float | Dip % from 7-day high to trigger buy |
| `buy_assets` | string[] | Which assets to buy-the-dip on |
| `buy_amount_eur` | float | EUR amount per buy order |
| `buy_cooldown_hours` | int | Min hours between buys per asset |

### Time-Fallback

| Field | Type | Description |
|-------|------|-------------|
| `enabled` | bool | Enable/disable the fallback mechanism |
| `max_idle_days` | int | Days without a buy before triggering fallback |
| `fallback_amount_eur` | float | Amount to buy on fallback |
| `fallback_assets` | string[] | Assets to buy on fallback |
| `require_dip` | bool | Only trigger fallback if price is already below the 7-day high |
| `min_dip_percent` | int | Minimum dip % required for fallback (when `require_dip` is true) |

### Fees

| Field | Type | Description |
|-------|------|-------------|
| `taker_fee_rate` | float | Coinbase taker fee (e.g. 0.012 for 1.2%) |
| `maker_fee_rate` | float | Coinbase maker fee (e.g. 0.006 for 0.6%) |

### Tracking

The bot auto-populates these fields — don't edit them manually:

- `position_tracking` — Entry price, amount, timestamp, partial sell totals
- `price_history` — Rolling price data for dip detection
- `sold_positions` — Record of sold positions for re-entry tracking
- `last_buy_timestamp` — For cooldown and fallback logic

### Analysis

| Field | Type | Description |
|-------|------|-------------|
| `enabled` | bool | Enable automatic periodic analysis |
| `frequency_days` | int | How often to run analysis |
| `min_positions_for_analysis` | int | Minimum positions before analysis runs |

## Usage

### Start the Bot

```bash
python trading_monitor.py
```

The bot will log to both console and `trading_monitor.log`. Press Ctrl+C to stop gracefully.

### Dry Run Mode

Set `"dry_run": true` in `trading_config.json` to test without real trades:
- All trades are simulated
- Budget tracking is maintained (virtual)
- No actual API orders are placed

### Periodic Analysis

When enabled, the bot runs an automatic analysis that:
1. Checks win rate, max gain/loss, average P&L
2. Suggests trigger adjustments based on performance
3. Writes recommendations to `trading_analysis.log` (never auto-applies)
4. Prints a console warning if changes ≥2% are recommended

Run manually:
```bash
python3 test_periodic_analysis.py
```

### Manual Analysis & Optimization

```bash
python3 analyze_performance.py    # Full P&L report + missed opportunities
python3 optimize_triggers.py      # Trigger optimization report
python3 dip_signal_analyzer.py --full  # Market signals (funding rates, liquidations, fear/greed)
```

## File Structure

```
trading_monitor.py        # Main monitoring loop (runs continuously)
coinbase_api.py           # Coinbase API wrapper
dip_signal_analyzer.py    # Market microstructure + macro signals
check_dip_signals.py      # Quick manual dip scan
analyze_performance.py    # Performance analysis
optimize_triggers.py      # Trigger optimizer
backtest.py               # Historical backtesting
test_*.py                 # Test scripts
trading_config.json       # Config (editable — not in git)
cdp_api_key.json          # API credentials (not in git)
trading_monitor.log       # Runtime log
trading_analysis.log      # Periodic analysis
price_history.db          # SQLite price history
```

## API Reference

### CoinbaseAPI

```python
from coinbase_api import CoinbaseAPI

api = CoinbaseAPI('cdp_api_key.json')

# Get current price
price_data = api.get_price('BTC')  # {'price': 93000, 'currency': 'USDC', ...}

# Get balances
accounts = api.get_accounts()
usdc_balance = api.get_balance('USDC')
eur_balance = api.get_balance('EUR')

# Place a market order
api.place_order('BTC-USDC', 'BUY', 10.0, 'quote_size')    # Buy $10 worth
api.place_order('BTC-USDC', 'SELL', 0.001, 'base_size')   # Sell 0.001 BTC
```

## Safety Features

- **Budget Protection**: Halts trading if USDC balance falls below minimum
- **Rate Limiting**: 10 requests/second max on Coinbase API
- **Retry Logic**: Automatic retries with exponential backoff
- **Precision Rounding**: Order sizes rounded to API requirements
- **Dry-Run Mode**: Strategy testing without real capital
- **Analysis Never Auto-Applys**: Recommendations are advisory only

## Logging

All activity is logged to `trading_monitor.log`:
- Trade executions (buy/sell)
- Position tracking updates
- Trigger activations
- API errors and retries

Console output provides real-time monitoring feedback.

## Known Issues

- **Insufficient funds**: Check real balance matches tracked budget
- **Invalid order size**: Bot auto-rounds, but minimum order sizes still apply
- **No buy triggers**: Need 7+ days of price history for dip detection
- **Tiny positions**: Very small holdings may fall below minimum order size
- **EURC dust**: Small leftover balances that can't be sold

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
**Maintained By**: Curt Galloway
