#!/usr/bin/env python3
"""
Dry-run script to simulate buying 1/3 BTC with EUR using Coinbase Advanced Trade API
"""
import json
import time
from coinbase_api import CoinbaseAPI, get_price_simple

# Initialize API
api = CoinbaseAPI()

def get_btc_eur_price():
    """Get current BTC/EUR price"""
    data = get_price_simple('BTC-EUR')
    
    if not data:
        print("Error fetching price")
        return None
    
    best_ask = float(data['best_ask'])
    print(f"Current BTC/EUR Ask Price: €{best_ask:,.2f}")
    return best_ask

def get_accounts():
    """Get account information (requires authentication)"""
    return api.get_accounts()

def simulate_buy_order(product_id="BTC-EUR", btc_amount=1/3):
    """
    Simulate a buy order (DRY RUN - does not execute)
    
    Args:
        product_id: Trading pair (default: BTC-EUR)
        btc_amount: Amount of BTC to buy (default: 0.333...)
    """
    print("\n" + "="*60)
    print("DRY RUN: Simulating BTC Purchase")
    print("="*60)
    
    # Get current price
    current_price = get_btc_eur_price()
    if not current_price:
        print("Cannot proceed without price information")
        return
    
    # Calculate order details
    total_cost = current_price * btc_amount
    
    print(f"\nOrder Details:")
    print(f"  Product: {product_id}")
    print(f"  Side: BUY")
    print(f"  Amount: {btc_amount:.8f} BTC")
    print(f"  Estimated Price: €{current_price:,.2f} per BTC")
    print(f"  Estimated Total Cost: €{total_cost:,.2f}")
    
    # Note: Actual API call would look like this (commented out for dry run):
    """
    order_payload = {
        "client_order_id": f"dry_run_{int(time.time())}",
        "product_id": product_id,
        "side": "BUY",
        "order_configuration": {
            "market_market_ioc": {
                "quote_size": str(total_cost)  # Buy EUR worth
                # OR use "base_size": str(btc_amount)  # Buy BTC amount
            }
        }
    }
    
    request_path = "/api/v3/brokerage/orders"
    token = create_jwt("POST", request_path)
    
    req = urllib.request.Request(
        f"{BASE_URL}{request_path}",
        data=json.dumps(order_payload).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        method="POST"
    )
    """
    
    print("\n⚠️  DRY RUN MODE - No actual order placed")
    print("\nTo execute a real order, you would:")
    print("1. Ensure you have sufficient EUR in your account")
    print("2. Use the /api/v3/brokerage/orders endpoint")
    print("3. Send a POST request with proper authentication")
    print("="*60)

if __name__ == "__main__":
    # Check if PyJWT is available
    try:
        import jwt
    except ImportError:
        print("Error: PyJWT library required")
        print("Install with: pip install PyJWT")
        exit(1)
    
    # Run dry-run simulation
    simulate_buy_order(btc_amount=1/3)
    
    print("\n\nOptional: Fetching account information...")
    accounts = get_accounts()
    if accounts:
        print(f"\nFound {len(accounts)} account(s):")
        for acc in accounts[:5]:  # Show first 5
            currency = acc.get('currency', 'N/A')
            balance = acc.get('available_balance', {}).get('value', '0')
            print(f"  {currency}: {balance}")
