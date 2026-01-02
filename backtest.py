#!/usr/bin/env python3
"""
Backtest trading strategy against current positions
Simulates what would have happened if the bot ran for the past 7 days
"""
import json
import logging
from coinbase_api import CoinbaseAPI

# Configure logging
logging.basicConfig(level=logging.WARNING)

# Initialize API (no authentication needed for price fetching)
api = CoinbaseAPI()

# Constants
USD_TO_EUR_FALLBACK = 0.92

def get_eur_usd_rate():
    """Get current EUR/USD exchange rate"""
    try:
        price_data = api.get_price('USDC', preferred_quotes=['EUR'])
        if price_data and price_data['currency'] == 'EUR':
            return price_data['price']
    except Exception:
        pass
    return USD_TO_EUR_FALLBACK

def get_price(asset):
    """Get current price for an asset"""
    price_data = api.get_price(asset)
    if price_data:
        return {'price': price_data['price'], 'currency': price_data['currency']}
    return None

# Load config
with open('trading_config.json', 'r') as f:
    config = json.load(f)

positions = config['position_tracking']
triggers = config['triggers']
fee_rate = config['fees']['taker_fee_rate']

# Get EUR/USD rate once at start
eur_usd_rate = get_eur_usd_rate()
print(f"\nUsing EUR/USD rate: {eur_usd_rate:.4f}")

print("="*70)
print("BACKTEST SIMULATION: Current vs Entry Prices")
print("="*70)
print(f"\nStrategy:")
print(f"  - Sell 50% at +{triggers['profit_target_percent']}%")
print(f"  - Sell 100% at +{triggers['final_profit_target_percent']}%")
print(f"  - Stop loss at -{triggers['stop_loss_percent']}%")
print(f"  - Fee rate: {fee_rate*100}%")
print(f"\nStarting budget: €{config['trading_budget_eur']:.2f}")
print("\n" + "="*70 + "\n")

total_profit = 0
trades_executed = 0
results = []

for asset, pos in positions.items():
    entry_price = pos['entry_price']
    entry_currency = pos['entry_currency']
    amount = pos['amount']
    
    # Get current price
    current_data = get_price(asset)
    
    if not current_data:
        print(f"⏭️  {asset}: No price data available")
        continue
    
    current_price = current_data['price']
    current_currency = current_data['currency']
    
    # For comparison, we need same currency
    if current_currency != entry_currency:
        # Convert both to EUR for comparison
        if entry_currency == 'USD':
            entry_price_eur = entry_price * eur_usd_rate
        else:
            entry_price_eur = entry_price
        
        if current_currency == 'USD':
            current_price_eur = current_price * eur_usd_rate
        else:
            current_price_eur = current_price
        
        pct_change = ((current_price_eur - entry_price_eur) / entry_price_eur) * 100
    else:
        # Calculate percentage change
        pct_change = ((current_price - entry_price) / entry_price) * 100
    
    # Calculate position values
    entry_value = amount * entry_price
    current_value = amount * current_price
    
    # Convert to EUR if needed
    if entry_currency == 'USD':
        entry_value_eur = entry_value * eur_usd_rate
    elif entry_currency in ['USDC', 'USDT']:
        entry_value_eur = entry_value * eur_usd_rate
    else:
        entry_value_eur = entry_value
    
    if current_currency == 'USD':
        current_value_eur = current_value * eur_usd_rate
    elif current_currency in ['USDC', 'USDT']:
        current_value_eur = current_value * eur_usd_rate
    else:
        current_value_eur = current_value
    
    print(f"{asset}:")
    print(f"  Entry: {entry_price:.8f} {entry_currency}")
    print(f"  Current: {current_price:.8f} {current_currency}")
    print(f"  Change: {pct_change:+.2f}%")
    print(f"  Value: €{current_value_eur:.4f}")
    
    # Check triggers
    profit_eur = 0
    trigger_hit = False
    
    if pct_change >= triggers['final_profit_target_percent']:
        # Sell 100% at +50%
        gross = current_value_eur
        fee = gross * fee_rate
        net = gross - fee
        profit_eur = net - entry_value_eur
        trades_executed += 1
        trigger_hit = True
        print(f"  🎯 FINAL PROFIT (+50%): Sell 100%")
        print(f"     Proceeds: €{net:.4f} | Profit: €{profit_eur:+.4f}")
        
    elif pct_change >= triggers['profit_target_percent']:
        # Sell 50% at +25%
        sell_amount = amount * 0.5
        gross = sell_amount * current_price
        if current_currency == 'USD':
            gross = gross * eur_usd_rate
        elif current_currency in ['USDC', 'USDT']:
            gross = gross * eur_usd_rate
        fee = gross * fee_rate
        net = gross - fee
        cost_basis = entry_value_eur * 0.5
        profit_eur = net - cost_basis
        trades_executed += 1
        trigger_hit = True
        print(f"  🎯 PROFIT TARGET (+25%): Sell 50%")
        print(f"     Proceeds: €{net:.4f} | Profit: €{profit_eur:+.4f}")
        
    elif pct_change <= -triggers['stop_loss_percent']:
        # Sell 100% at -15%
        gross = current_value_eur
        fee = gross * fee_rate
        net = gross - fee
        profit_eur = net - entry_value_eur
        trades_executed += 1
        trigger_hit = True
        print(f"  🔴 STOP LOSS (-15%): Sell 100%")
        print(f"     Proceeds: €{net:.4f} | Loss: €{profit_eur:+.4f}")
    else:
        print(f"  ⏸️  No trigger (need {triggers['profit_target_percent']}% gain or {triggers['stop_loss_percent']}% loss)")
    
    total_profit += profit_eur
    results.append({
        'asset': asset,
        'pct_change': pct_change,
        'profit': profit_eur,
        'trigger': trigger_hit
    })
    print()

print("="*70)
print("SUMMARY")
print("="*70)
print(f"Assets analyzed: {len(results)}")
print(f"Triggers hit: {trades_executed}")
print(f"Triggers missed: {len(results) - trades_executed}")
print()
print(f"Starting budget: €{config['trading_budget_eur']:.2f}")
print(f"Simulated P&L: €{total_profit:+.4f}")
print(f"Final budget: €{config['trading_budget_eur'] + total_profit:.2f}")
if config['trading_budget_eur'] > 0:
    print(f"Return: {(total_profit / config['trading_budget_eur'] * 100):+.2f}%")
print("="*70)

if trades_executed == 0:
    print("\n📊 Analysis:")
    print("No triggers were hit. This means:")
    print("  - Your assets haven't moved ±25% or more since entry")
    print("  - The market has been relatively stable")
    print("  - Your trigger levels might need adjustment for more activity")
    
    # Show which assets were closest to triggers
    print("\nClosest to triggers:")
    sorted_results = sorted(results, key=lambda x: abs(x['pct_change']), reverse=True)
    for r in sorted_results[:5]:
        print(f"  {r['asset']}: {r['pct_change']:+.2f}%")
else:
    print("\n✅ Triggers activated! The strategy would have executed trades.")
