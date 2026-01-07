# Crypto Trading Monitor Bot

An automated cryptocurrency trading bot for Coinbase Advanced Trade API that implements profit-taking, stop-loss, and buy-the-dip strategies.

## Features

### Trading Strategies

- **Profit Taking**: Automatically sells 50% of a position when it reaches +25% profit
- **Final Profit Target**: Sells 100% of remaining position at +50% profit
- **Stop Loss**: Protects against losses by selling 100% at -15%
- **Buy-the-Dip**: Automatically buys BTC/ETH when price dips 5-7% from 7-day high
- **Re-Entry Logic**: Buys back sold positions when price dips 10-15% below sale price

### Risk Management

- Budget tracking to prevent over-trading
- Minimum balance protection
- Position tracking with entry price and P&L calculations
- Configurable trading fees (taker/maker rates)
- Dry-run mode for testing strategies without real trades

### Monitoring

- Continuous monitoring at configurable intervals (default: 15 minutes)
- Real-time portfolio tracking across multiple assets
- Price history tracking over 7-day rolling window
- Comprehensive logging to file and console
- Currency conversion support (USD, EUR, USDC, USDT)

## Requirements

- Python 3.7+
- Coinbase Advanced Trade API credentials
- Required Python packages:
  - PyJWT (for API authentication)

## Installation

1. Clone this repository:
```bash
git clone <repository-url>
cd trading-bot
```

2. Create a virtual environment and activate it:
```bash
python3 -m venv venv
source venv/bin/activate  # On Linux/Mac
# or
venv\Scripts\activate  # On Windows
```

3. Install dependencies:
```bash
pip install PyJWT
```

4. Set up your Coinbase API credentials:
   - Create a CDP API key from Coinbase
   - Save the credentials to `cdp_api_key.json` in the project directory

5. Configure your trading parameters in `trading_config.json`

## Configuration

### trading_config.json

```json
{
  "trading_budget_eur": 50.0,           // Total budget to trade with
  "minimum_balance_eur": 5.0,           // Stop trading if budget falls below this
  "check_interval_minutes": 15,         // How often to check positions
  "dry_run": false,                     // Set to true for testing without real trades
  
  "triggers": {
    "profit_target_percent": 25,        // Sell 50% at this profit level
    "profit_target_sell_percent": 50,   // Percentage to sell at profit target
    "final_profit_target_percent": 50,  // Sell 100% at this profit level
    "stop_loss_percent": 15,            // Sell 100% if loss reaches this
    "buy_dip_percent": 5,               // Buy when price dips this much
    "buy_assets": ["BTC", "ETH"],       // Assets to buy-the-dip on
    "buy_amount_eur": 10                // Amount in EUR for each buy
  },
  
  "fees": {
    "taker_fee_rate": 0.012,            // Coinbase taker fee (1.2%)
    "maker_fee_rate": 0.006             // Coinbase maker fee (0.6%)
  },
  
  "tracked_assets": [                   // Assets to monitor and trade
    "BTC", "ETH", "PEPE", "VET", ...
  ],
  
  "position_tracking": {},              // Auto-populated with positions
  "price_history": {},                  // Auto-populated with price data
  "sold_positions": {}                  // Auto-populated for re-entry tracking
}
```

## Usage

### Start the Trading Bot

```bash
python trading_monitor.py
```

The bot will:
1. Load configuration and validate settings
2. Connect to Coinbase API
3. Start monitoring cycle at configured interval
4. Execute trades based on trigger conditions
5. Log all activity to `trading_monitor.log`

### Stop the Bot

Press `Ctrl+C` to gracefully stop the monitoring loop.

### Dry Run Mode

To test the bot without executing real trades, set `"dry_run": true` in `trading_config.json`:

```json
{
  "dry_run": true,
  ...
}
```

In dry-run mode:
- All trades are simulated
- Budget tracking is maintained
- No actual API orders are placed
- Useful for strategy testing

## File Structure

```
coinbase/
├── trading_monitor.py      # Main bot script with monitoring loop
├── coinbase_api.py          # Coinbase API wrapper and utilities
├── trading_config.json      # Trading configuration (user-editable)
├── cdp_api_key.json         # API credentials (not in git)
├── trading_monitor.log      # Runtime log file
├── get_btc_price.py         # Utility to check current BTC price
├── backtest.py              # Backtesting utilities
├── test_*.py                # Various test scripts
└── README.md                # This file
```

## How It Works

### Monitoring Cycle

1. **Check Holdings**: Fetches current portfolio from Coinbase
2. **Track Prices**: Records current prices for buy-the-dip detection
3. **Check Sell Triggers**: For each position, checks if profit/loss targets are hit
4. **Execute Sells**: Places market sell orders when triggers activate
5. **Check Buy Triggers**: Looks for dip-buying and re-entry opportunities
6. **Execute Buys**: Places market buy orders for qualified opportunities
7. **Update Tracking**: Saves position and price data
8. **Sleep**: Waits for next cycle interval

### Position Tracking

When you acquire a position (either manually or via the bot), the bot tracks:
- Entry price and currency
- Entry timestamp
- Position size
- Partial sells (for staged profit-taking)

### Price History

The bot maintains a 7-day rolling window of prices for configured buy assets:
- Used to calculate 7-day highs
- Enables buy-the-dip detection
- Automatically cleaned up after 7 days

### Sold Position Tracking

When a position is fully sold:
- Sale price and timestamp recorded
- Tracked for 30 days for re-entry opportunities
- Automatically expires after 30 days

## API Reference

### CoinbaseAPI Class

```python
from coinbase_api import CoinbaseAPI

api = CoinbaseAPI('cdp_api_key.json')

# Get current price
price_data = api.get_price('BTC')  # Returns {'price': 93000, 'currency': 'USDC', ...}

# Get account balances
accounts = api.get_accounts()

# Get specific currency balance
eur_balance = api.get_balance('EUR')

# Place a market order
api.place_order('BTC-EUR', 'BUY', 100.0, 'quote_size')  # Buy €100 worth of BTC
api.place_order('BTC-EUR', 'SELL', 0.001, 'base_size')  # Sell 0.001 BTC
```

## Safety Features

- **Budget Protection**: Stops trading if budget falls below minimum
- **Rate Limiting**: Built-in API rate limiting (10 req/second max)
- **Retry Logic**: Automatic retries with exponential backoff
- **Precision Rounding**: Proper order size rounding to prevent API rejections
- **Error Logging**: Comprehensive error logging for debugging
- **Dry-Run Testing**: Test strategies without risking capital

## Logging

All activity is logged to `trading_monitor.log`:
- Trade executions (buy/sell)
- Position tracking updates
- Trigger activations
- API errors and retries
- Configuration changes

Console output provides real-time monitoring feedback.

## Common Issues

### "Insufficient funds" errors
- Check your actual balance matches tracked budget
- Ensure minimum balance protection isn't too high
- Verify fee calculations are accurate

### "Invalid order size" errors
- The bot automatically rounds to correct precision
- Check that buy amounts meet minimum order sizes
- Ensure product is available for trading

### No buy triggers activating
- Need 7 days of price history for buy-the-dip
- Verify price is within 5-7% dip range
- Check that asset isn't already held (no duplicate buys)

## Disclaimer

This bot is for educational purposes. Cryptocurrency trading carries significant risk:
- You can lose all your invested capital
- Past performance doesn't guarantee future results
- Test thoroughly in dry-run mode before live trading
- Start with small amounts you can afford to lose
- Monitor the bot regularly - automation doesn't mean "set and forget"

**Use at your own risk. The authors take no responsibility for any financial losses.**

## License

This project is provided as-is for educational and personal use.

## Contributing

This is a personal trading bot. Feel free to fork and modify for your own use.

## Support

For issues with:
- **Coinbase API**: Check [Coinbase Developer Documentation](https://docs.cloud.coinbase.com/)
- **This Bot**: Review logs in `trading_monitor.log` and enable debug logging if needed
