#!/usr/bin/env python3
"""
Diagnostic script to troubleshoot "account is not available" errors
Lists all accounts, trading products, and checks availability
"""
import json
from coinbase_api import CoinbaseAPI

def main():
    api = CoinbaseAPI()

    print("\n" + "="*70)
    print("COINBASE ACCOUNT DIAGNOSTIC TOOL")
    print("="*70)

    # 1. Get all accounts
    print("\n📊 FETCHING ACCOUNTS...")
    accounts = api.get_accounts()

    if not accounts:
        print("❌ ERROR: Could not fetch accounts!")
        print("   This suggests an API authentication issue.")
        return

    print(f"\n✅ Found {len(accounts)} account(s)\n")

    # Load config to see which assets we're tracking
    try:
        with open('trading_config.json', 'r') as f:
            config = json.load(f)
        tracked_assets = config.get('tracked_assets', [])
        positions = config.get('position_tracking', {})
    except FileNotFoundError:
        print("⚠️  Warning: trading_config.json not found")
        tracked_assets = []
        positions = {}

    # 2. Display accounts with focus on tracked assets
    print("ACCOUNT DETAILS:")
    print("-" * 70)

    tracked_accounts = []
    other_accounts = []

    for acc in accounts:
        currency = acc.get('currency', 'N/A')
        uuid = acc.get('uuid', 'N/A')
        balance = acc.get('available_balance', {}).get('value', '0')
        hold_balance = acc.get('hold', {}).get('value', '0')
        account_type = acc.get('type', 'N/A')
        ready = acc.get('ready', False)

        account_info = {
            'currency': currency,
            'uuid': uuid,
            'balance': float(balance),
            'hold': float(hold_balance),
            'type': account_type,
            'ready': ready
        }

        if currency in tracked_assets or float(balance) > 0:
            tracked_accounts.append(account_info)
        else:
            other_accounts.append(account_info)

    # Show tracked/non-zero accounts first
    print("\n🎯 TRACKED ASSETS & NON-ZERO BALANCES:")
    for acc in tracked_accounts:
        status = "✅ READY" if acc['ready'] else "⚠️  NOT READY"
        hold_info = f" (Hold: {acc['hold']:.8f})" if acc['hold'] > 0 else ""
        print(f"\n  {acc['currency']}:")
        print(f"    UUID: {acc['uuid']}")
        print(f"    Balance: {acc['balance']:.8f}{hold_info}")
        print(f"    Type: {acc['type']}")
        print(f"    Status: {status}")

        # Check if this asset has position tracking
        if acc['currency'] in positions:
            pos = positions[acc['currency']]
            print(f"    Entry: {pos['entry_price']} {pos['entry_currency']}")

    # 3. Check available trading products for tracked assets
    print("\n" + "="*70)
    print("CHECKING TRADING PRODUCTS...")
    print("="*70)

    for asset in tracked_assets:
        if asset in [acc['currency'] for acc in tracked_accounts]:
            print(f"\n{asset}:")

            # Try different quote currencies
            quote_currencies = ['EUR', 'USDC', 'USD', 'USDT']
            available_pairs = []

            for quote in quote_currencies:
                pair = f"{asset}-{quote}"
                result = api.api_request("GET", f"/api/v3/brokerage/market/products/{pair}")

                if result:
                    status = result.get('status', 'UNKNOWN')
                    trading_disabled = result.get('trading_disabled', True)

                    if status == 'online' and not trading_disabled:
                        available_pairs.append(quote)
                        print(f"  ✅ {pair}: Available for trading")
                    else:
                        print(f"  ❌ {pair}: Status={status}, Disabled={trading_disabled}")

            if not available_pairs:
                print(f"  ⚠️  WARNING: No tradeable pairs found for {asset}!")
            else:
                print(f"  💡 Can trade on: {', '.join([f'{asset}-{q}' for q in available_pairs])}")

    # 4. Test order validation (without placing)
    print("\n" + "="*70)
    print("ORDER VALIDATION TEST")
    print("="*70)
    print("\nAttempting to validate order structure...")
    print("(This will NOT place actual orders)")

    # Show what a valid order should look like
    print("\nValid order format:")
    print(json.dumps({
        "client_order_id": "test_order",
        "product_id": "BTC-EUR",
        "side": "SELL",
        "order_configuration": {
            "market_market_ioc": {
                "base_size": "0.001"
            }
        }
    }, indent=2))

    # 5. Summary and recommendations
    print("\n" + "="*70)
    print("DIAGNOSTIC SUMMARY")
    print("="*70)

    not_ready_accounts = [acc for acc in tracked_accounts if not acc['ready']]
    zero_balance_tracked = [asset for asset in tracked_assets
                           if asset not in [acc['currency'] for acc in tracked_accounts]]

    print(f"\n✅ Total accounts accessible: {len(accounts)}")
    print(f"✅ Tracked assets with balance: {len(tracked_accounts)}")

    if not_ready_accounts:
        print(f"\n⚠️  ISSUE FOUND: {len(not_ready_accounts)} account(s) not ready:")
        for acc in not_ready_accounts:
            print(f"   - {acc['currency']}: Status is NOT READY")
        print("\n   This could be why orders are failing!")
        print("   Possible causes:")
        print("   - Account needs verification")
        print("   - Asset is in wrong portfolio/wallet")
        print("   - Account is restricted or locked")

    if zero_balance_tracked:
        print(f"\n⚠️  NOTE: {len(zero_balance_tracked)} tracked asset(s) have zero balance:")
        for asset in zero_balance_tracked[:5]:
            print(f"   - {asset}")

    print("\n💡 RECOMMENDATIONS:")
    print("   1. Check that 'ready' status is true for all assets you want to trade")
    print("   2. Verify assets are in your 'Primary' portfolio")
    print("   3. Log into Coinbase web interface and check for any account restrictions")
    print("   4. Ensure you're using Coinbase Advanced Trade (not Coinbase Pro or Wallet)")
    print("   5. Check if any assets are locked in staking or earning programs")

    print("\n" + "="*70 + "\n")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
