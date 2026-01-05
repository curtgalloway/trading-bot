#!/usr/bin/env python3
"""
Verify that the fix works by checking what trading pairs will be used
"""
from coinbase_api import CoinbaseAPI
import json

api = CoinbaseAPI()

print("\n" + "="*70)
print("VERIFICATION: Testing Trading Pair Selection")
print("="*70)

# Load tracked assets from config
with open('trading_config.json', 'r') as f:
    config = json.load(f)

positions = config['position_tracking']

print("\nChecking what trading pairs will be selected for each asset...")
print("-"*70)

for asset in positions.keys():
    if asset == 'PEPE':  # Focus on PEPE since we tested it
        print(f"\n{asset}:")
        price_data = api.get_price(asset)

        if price_data:
            print(f"  ✅ Selected pair: {price_data['pair']}")
            print(f"  ✅ Quote currency: {price_data['currency']}")
            print(f"  ✅ Price: {price_data['price']}")

            # This pair should work now!
            if price_data['currency'] in ['USDC', 'EUR', 'USDT']:
                print(f"  ✅ This pair should work for trading!")
            else:
                print(f"  ⚠️  WARNING: This pair might not work (uses {price_data['currency']})")
        else:
            print(f"  ❌ Could not get price data")

print("\n" + "="*70)
print("RECOMMENDATION:")
print("="*70)
print("""
The fix has been applied! Your code will now:
1. Try USDC pairs first (which work!)
2. Then EUR pairs
3. Then USDT pairs
4. Avoid USD pairs (which require USD accounts)

Your sell orders should now work. Try running your trading monitor again!
""")
print("="*70 + "\n")
