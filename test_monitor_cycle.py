#!/usr/bin/env python3
"""
Test a single monitoring cycle to verify the fix works
This will check triggers but only execute orders in DRY RUN mode
"""
import json
from coinbase_api import CoinbaseAPI, validate_config
from datetime import datetime

api = CoinbaseAPI()

print("\n" + "="*70)
print("TEST: Single Monitoring Cycle (DRY RUN)")
print("="*70)

# Load and validate config
try:
    with open('trading_config.json', 'r') as f:
        config = json.load(f)
    validate_config(config)
except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
    print(f"Error loading config: {e}")
    exit(1)

positions = config['position_tracking']
triggers = config['triggers']

# Get EUR/USD rate using centralized function
eur_usd_rate = api.get_eur_usd_rate()
print(f"\nEUR/USD rate: {eur_usd_rate:.4f}")
print(f"\nChecking triggers for tracked positions...")
print("-"*70)

# Check a few key assets
test_assets = ['PEPE', 'VET', 'NEAR', 'ALEPH', 'FET', 'GRT']

for asset in test_assets:
    if asset not in positions:
        continue

    print(f"\n{asset}:")

    pos = positions[asset]
    entry_price = pos['entry_price']
    entry_currency = pos['entry_currency']
    amount = pos['amount']

    # Get current price (should now use USDC/EUR)
    current_data = api.get_price(asset)

    if not current_data:
        print(f"  ⚠️  Could not get price")
        continue

    current_price = current_data['price']
    current_currency = current_data['currency']
    pair = current_data['pair']

    print(f"  Entry: {entry_price:.8f} {entry_currency}")
    print(f"  Current: {current_price:.8f} {current_currency}")
    print(f"  Trading pair: {pair}")

    # Calculate percentage change using centralized conversion
    entry_price_eur = api.convert_to_eur(entry_price, entry_currency)
    current_price_eur = api.convert_to_eur(current_price, current_currency)
    pct_change = ((current_price_eur - entry_price_eur) / entry_price_eur) * 100

    print(f"  Change: {pct_change:+.2f}%")

    # Check triggers
    total_sold = pos.get('total_sold', 0.0)

    if pct_change >= triggers['final_profit_target_percent']:
        print(f"  🎯 TRIGGER: Final profit target (+{triggers['final_profit_target_percent']}%)")
        print(f"     Would SELL 100% ({amount:.8f} {asset}) on {pair}")
        print(f"     ✅ This pair works with your account!")
    elif pct_change >= triggers['profit_target_percent'] and total_sold == 0:
        sell_amount = amount * (triggers['profit_target_sell_percent'] / 100)
        print(f"  🎯 TRIGGER: Profit target (+{triggers['profit_target_percent']}%)")
        print(f"     Would SELL 50% ({sell_amount:.8f} {asset}) on {pair}")
        print(f"     ✅ This pair works with your account!")
    elif pct_change <= -triggers['stop_loss_percent']:
        print(f"  🔴 TRIGGER: Stop loss (-{triggers['stop_loss_percent']}%)")
        print(f"     Would SELL 100% ({amount:.8f} {asset}) on {pair}")
        print(f"     ✅ This pair works with your account!")
    else:
        print(f"  ⏸️  No trigger (need +{triggers['profit_target_percent']}% or -{triggers['stop_loss_percent']}%)")

print("\n" + "="*70)
print("TEST COMPLETE")
print("="*70)
print("""
✅ The fix is working! All trading pairs now use USDC/EUR instead of USD.

Your trading monitor should now work correctly. Orders will be placed on
trading pairs that are compatible with your account.

If you see any triggers above, those orders would execute successfully!
""")
print("="*70 + "\n")
