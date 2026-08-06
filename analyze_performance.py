#!/usr/bin/env python3
"""
Trading Performance Analysis Script
Analyzes actual trades, missed opportunities, and profitability
"""

import json
from datetime import datetime
from coinbase_api import CoinbaseAPI

def analyze_trading_performance():
    # Load configuration
    with open('trading_config.json', 'r') as f:
        config = json.load(f)
    
    api = CoinbaseAPI()
    
    print("=" * 80)
    print("TRADING BOT PERFORMANCE ANALYSIS")
    print("=" * 80)
    print()
    
    # 1. Current Portfolio Status
    print("📊 CURRENT PORTFOLIO STATUS")
    print("-" * 80)
    
    total_invested_usd = 0
    current_value_usd = 0
    positions_summary = []
    
    for symbol, pos_data in config['position_tracking'].items():
        amount = pos_data['amount']
        entry_price = pos_data['entry_price']
        entry_currency = pos_data['entry_currency']
        total_sold = pos_data.get('total_sold', 0)
        
        # Get current price
        try:
            price_data = api.get_price(symbol, preferred_quotes=['USDC', 'USD'])
            if not price_data:
                raise Exception("No price data available")
            current_price = price_data['price']
            
            # Calculate invested amount (in USD/USDC)
            if entry_currency == "EUR":
                # Approximate EUR to USD at ~1.17
                invested = amount * entry_price * 1.17
            else:
                invested = amount * entry_price
            
            # Current value
            current_val = amount * current_price
            
            # Profit/Loss
            pnl = current_val - invested
            pnl_percent = (pnl / invested * 100) if invested > 0 else 0
            
            total_invested_usd += invested
            current_value_usd += current_val
            
            positions_summary.append({
                'symbol': symbol,
                'amount': amount,
                'entry_price': entry_price,
                'current_price': current_price,
                'invested': invested,
                'current_value': current_val,
                'pnl': pnl,
                'pnl_percent': pnl_percent,
                'sold': total_sold
            })
            
        except Exception as e:
            print(f"⚠️  Error getting price for {symbol}: {e}")
    
    # Sort by PnL percentage
    positions_summary.sort(key=lambda x: x['pnl_percent'], reverse=True)
    
    print(f"{'Asset':<8} {'Amount':<12} {'Entry $':<10} {'Current $':<10} {'P&L $':<10} {'P&L %':<10} {'Sold':<8}")
    print("-" * 80)
    
    for pos in positions_summary:
        color = "🟢" if pos['pnl_percent'] > 0 else "🔴" if pos['pnl_percent'] < 0 else "⚪"
        print(f"{color} {pos['symbol']:<6} {pos['amount']:<12.4f} ${pos['entry_price']:<9.4f} "
              f"${pos['current_price']:<9.4f} ${pos['pnl']:<9.2f} {pos['pnl_percent']:>6.2f}%  "
              f"{pos['sold']:.1f}")
    
    print("-" * 80)
    total_pnl = current_value_usd - total_invested_usd
    total_pnl_percent = (total_pnl / total_invested_usd * 100) if total_invested_usd > 0 else 0
    
    print(f"{'TOTAL':<8} {'':<12} ${total_invested_usd:<9.2f} ${current_value_usd:<9.2f} "
          f"${total_pnl:<9.2f} {total_pnl_percent:>6.2f}%")
    print()
    
    # 2. Budget Analysis
    print("💰 BUDGET ANALYSIS")
    print("-" * 80)
    
    try:
        # Use the API request method to get accounts
        accounts_data = api._api_request('GET', '/api/v3/brokerage/accounts')
        accounts = accounts_data.get('accounts', [])
        usdc_balance = 0
        
        for account in accounts:
            if account.get('currency') == 'USDC':
                usdc_balance = float(account.get('available_balance', {}).get('value', 0))
                break
        
        budget_eur = config['trading_budget_eur']
        budget_usd = budget_eur * 1.17  # Approximate
        min_balance_eur = config['minimum_balance_eur']
        min_balance_usd = min_balance_eur * 1.17
        
        print(f"Total Trading Budget:     €{budget_eur:.2f} (~${budget_usd:.2f})")
        print(f"Minimum Reserve:          €{min_balance_eur:.2f} (~${min_balance_usd:.2f})")
        print(f"Current USDC Balance:     ${usdc_balance:.2f}")
        print(f"Deployed in Positions:    ${total_invested_usd:.2f}")
        print(f"Total Capital (USDC):     ${usdc_balance + total_invested_usd:.2f}")
        print()
        
        # Calculate how much has been consumed
        initial_capital = budget_usd
        remaining_pct = (usdc_balance / initial_capital * 100) if initial_capital > 0 else 0
        deployed_pct = (total_invested_usd / initial_capital * 100) if initial_capital > 0 else 0
        
        print(f"Capital Utilization:")
        print(f"  - Deployed:    {deployed_pct:>6.1f}%")
        print(f"  - Available:   {remaining_pct:>6.1f}%")
        print()
        
    except Exception as e:
        print(f"⚠️  Error fetching account data: {e}")
        print()
    
    # 3. Actual Trades Analysis
    print("📈 COMPLETED TRADES")
    print("-" * 80)
    
    # Parse log file for actual executed trades
    executed_buys = 0
    executed_sells = 0
    
    try:
        with open('trading_monitor.log', 'r') as f:
            for line in f:
                if 'BUY order success' in line:
                    executed_buys += 1
                    # Extract details if possible
                    if 'ETH' in line:
                        print(f"✅ BUY:  {line.split('INFO - ')[1].strip()}")
                    elif 'VARA' in line:
                        print(f"✅ BUY:  {line.split('INFO - ')[1].strip()}")
                elif 'SELL order success' in line:
                    executed_sells += 1
                    print(f"💵 SELL: {line.split('INFO - ')[1].strip()}")
    except:
        pass
    
    print()
    print(f"Total BUY orders executed:   {executed_buys}")
    print(f"Total SELL orders executed:  {executed_sells}")
    print()
    
    # 4. Missed Opportunities Analysis
    print("⚠️  MISSED OPPORTUNITIES (Insufficient Funds)")
    print("-" * 80)
    
    missed_opportunities = []
    
    try:
        with open('trading_monitor.log', 'r') as f:
            for line in f:
                if 'Insufficient budget for buy' in line:
                    timestamp = line.split(' - ')[0]
                    asset = line.split('buy: ')[1].split(',')[0]
                    missed_opportunities.append({'time': timestamp, 'asset': asset})
    except:
        pass
    
    # Count by asset
    missed_by_asset = {}
    for opp in missed_opportunities:
        asset = opp['asset']
        missed_by_asset[asset] = missed_by_asset.get(asset, 0) + 1
    
    print(f"Total missed opportunities: {len(missed_opportunities)}")
    print()
    print("Breakdown by asset:")
    for asset, count in sorted(missed_by_asset.items(), key=lambda x: x[1], reverse=True):
        print(f"  {asset}: {count} times")
    
    if missed_opportunities:
        print()
        print(f"First missed: {missed_opportunities[0]['time']}")
        print(f"Last missed:  {missed_opportunities[-1]['time']}")
    
    print()
    
    # 5. Recommendations
    print("💡 RECOMMENDATIONS")
    print("-" * 80)
    
    print()
    print("RISK ASSESSMENT:")
    
    if total_pnl_percent > 0:
        print(f"✅ Currently PROFITABLE: +{total_pnl_percent:.2f}% (${total_pnl:.2f})")
        print(f"   Adding more capital makes sense IF you believe the strategy will continue.")
    elif total_pnl_percent > -5:
        print(f"⚠️  Near break-even: {total_pnl_percent:.2f}% (${total_pnl:.2f})")
        print(f"   Strategy hasn't proven itself yet. Adding capital is RISKY.")
    else:
        print(f"🔴 Currently LOSING: {total_pnl_percent:.2f}% (${total_pnl:.2f})")
        print(f"   DO NOT add more capital until strategy is fixed!")
    
    print()
    print("MISSED OPPORTUNITY ANALYSIS:")
    
    if len(missed_opportunities) > 50:
        print(f"🔴 HIGH: {len(missed_opportunities)} missed trades")
        print(f"   You're missing a LOT of opportunities. However, consider:")
        print(f"   - Are these QUALITY opportunities?")
        print(f"   - Would taking all trades actually be profitable?")
        print(f"   - Maybe running out of funds is PROTECTING you from losses?")
    elif len(missed_opportunities) > 20:
        print(f"⚠️  MODERATE: {len(missed_opportunities)} missed trades")
        print(f"   Some opportunities missed, but not excessive.")
    else:
        print(f"✅ LOW: {len(missed_opportunities)} missed trades")
        print(f"   Budget seems adequate for current strategy.")
    
    print()
    print("FINAL VERDICT:")
    print()
    
    # Calculate win rate from positions
    winning_positions = sum(1 for p in positions_summary if p['pnl_percent'] > 0)
    total_positions = len(positions_summary)
    win_rate = (winning_positions / total_positions * 100) if total_positions > 0 else 0
    
    print(f"Current Win Rate: {winning_positions}/{total_positions} = {win_rate:.1f}%")
    print()
    
    if total_pnl_percent > 5 and win_rate > 50:
        print("✅ RECOMMENDATION: CAUTIOUSLY ADD MORE CAPITAL")
        print("   Your strategy is showing positive results.")
        print(f"   Suggest adding: ${budget_usd * 0.5:.2f} to ${budget_usd:.2f}")
    elif total_pnl_percent > 0:
        print("⚠️  RECOMMENDATION: WAIT AND MONITOR")
        print("   Strategy is slightly profitable but not proven yet.")
        print("   Let current positions play out before adding more capital.")
    else:
        print("🔴 RECOMMENDATION: DO NOT ADD MORE CAPITAL YET")
        print("   Current strategy is not profitable.")
        print("   Focus on:")
        print("   1. Analyzing WHY you're losing money")
        print("   2. Adjusting parameters (buy_dip_percent, profit_target, etc.)")
        print("   3. Testing changes with small amounts first")
    
    print()
    print("=" * 80)

if __name__ == "__main__":
    analyze_trading_performance()
