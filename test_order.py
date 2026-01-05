#!/usr/bin/env python3
"""
Test order placement to get detailed error messages
Tests a tiny order to diagnose the "account is not available" error
"""
from coinbase_api import CoinbaseAPI
import json

api = CoinbaseAPI()

print("\n" + "="*70)
print("TEST ORDER PLACEMENT - Diagnostic Mode")
print("="*70)

# Get PEPE balance
accounts = api.get_accounts()
pepe_account = None
for acc in accounts:
    if acc.get('currency') == 'PEPE':
        pepe_account = acc
        break

if not pepe_account:
    print("❌ No PEPE account found!")
    exit(1)

print(f"\n✅ Found PEPE account:")
print(f"   UUID: {pepe_account['uuid']}")
print(f"   Balance: {pepe_account['available_balance']['value']} PEPE")
print(f"   Ready: {pepe_account.get('ready', False)}")
print(f"   Type: {pepe_account.get('type', 'N/A')}")

# Test 1: Try placing a very small sell order on PEPE-USDC
print("\n" + "-"*70)
print("TEST 1: Attempting SELL order on PEPE-USDC")
print("-"*70)

# Use a very small amount
test_amount = 1.0  # Just 1 PEPE token

order_data = {
    "client_order_id": f"test_sell_{int(__import__('time').time())}",
    "product_id": "PEPE-USDC",
    "side": "SELL",
    "order_configuration": {
        "market_market_ioc": {
            "base_size": str(test_amount)
        }
    }
}

print(f"\nOrder payload:")
print(json.dumps(order_data, indent=2))

print(f"\nAttempting to place order...")
result = api.api_request("POST", "/api/v3/brokerage/orders", order_data)

if result:
    print(f"\n✅ ORDER SUCCESSFUL!")
    print(json.dumps(result, indent=2))
    print("\n⚠️  This was a REAL order! Check your Coinbase account.")
else:
    print(f"\n❌ ORDER FAILED")
    print("Check the error messages above for details.")

# Test 2: Try with PEPE-USD instead
print("\n" + "-"*70)
print("TEST 2: Attempting SELL order on PEPE-USD")
print("-"*70)

order_data['product_id'] = "PEPE-USD"
order_data['client_order_id'] = f"test_sell_usd_{int(__import__('time').time())}"

print(f"\nOrder payload:")
print(json.dumps(order_data, indent=2))

print(f"\nAttempting to place order...")
result = api.api_request("POST", "/api/v3/brokerage/orders", order_data)

if result:
    print(f"\n✅ ORDER SUCCESSFUL!")
    print(json.dumps(result, indent=2))
    print("\n⚠️  This was a REAL order! Check your Coinbase account.")
else:
    print(f"\n❌ ORDER FAILED")
    print("Check the error messages above for details.")

print("\n" + "="*70)
print("DIAGNOSTIC COMPLETE")
print("="*70)
print("\nIf both tests failed, the issue is likely:")
print("  1. Regional trading restrictions")
print("  2. Account verification requirements")
print("  3. API limitations on specific assets")
print("  4. Advanced Trade not fully enabled")
print("\nNext step: Check Coinbase web interface for any notices or restrictions.")
print("="*70 + "\n")
