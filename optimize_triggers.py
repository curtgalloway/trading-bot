#!/usr/bin/env python3
"""
Analyze current positions and historical performance to suggest optimal trading triggers.
"""

import json
from datetime import datetime
from coinbase_api import CoinbaseAPI
import time

def load_config():
    """Load trading configuration."""
    with open('trading_config.json', 'r') as f:
        return json.load(f)

def analyze_position_performance(config):
    """Analyze each position's current performance and optimal triggers."""
    
    positions = config.get('position_tracking', {})
    triggers = config.get('triggers', {})
    api = CoinbaseAPI()
    
    print("=" * 80)
    print("POSITION PERFORMANCE ANALYSIS")
    print("=" * 80)
    print()
    
    total_investment_usd = 0
    total_current_value_usd = 0
    position_data = []
    
    for asset, pos_info in positions.items():
        if pos_info['amount'] == 0 or pos_info.get('too_small_to_sell'):
            continue
            
        print(f"\n{asset}:")
        print(f"  Entry Price: {pos_info['entry_price']} {pos_info['entry_currency']}")
        print(f"  Amount: {pos_info['amount']}")
        print(f"  Entry Time: {pos_info['entry_time']}")
        
        # Get current price
        try:
            price_data = api.get_price(asset)
            if not price_data:
                raise Exception("Could not fetch price")
            current_price = price_data['price']
            time.sleep(0.2)  # Rate limiting
            
            # Calculate investment value (convert to USD if needed)
            entry_currency = pos_info['entry_currency']
            entry_price = pos_info['entry_price']
            
            # Simple approximation - treat EUR ≈ USD for analysis
            investment_value = entry_price * pos_info['amount']
            current_value = current_price * pos_info['amount']
            
            profit_loss_pct = ((current_price - entry_price) / entry_price) * 100
            profit_loss_value = current_value - investment_value
            
            total_investment_usd += investment_value
            total_current_value_usd += current_value
            
            print(f"  Current Price: {current_price:.6f} {entry_currency}")
            print(f"  Current Value: ${current_value:.2f}")
            print(f"  P&L: {profit_loss_pct:+.2f}% (${profit_loss_value:+.2f})")
            
            # Analyze what would have happened with different triggers
            status = "🔴 LOSS" if profit_loss_pct < 0 else "🟢 PROFIT"
            print(f"  Status: {status}")
            
            # Would current triggers have worked?
            would_sell_first = profit_loss_pct >= triggers['profit_target_percent']
            would_sell_final = profit_loss_pct >= triggers['final_profit_target_percent']
            would_stop_loss = profit_loss_pct <= -triggers['stop_loss_percent']
            
            if would_sell_first:
                print(f"  ✓ Would hit first profit target ({triggers['profit_target_percent']}%)")
            elif would_sell_final:
                print(f"  ✓ Would hit final profit target ({triggers['final_profit_target_percent']}%)")
            elif would_stop_loss:
                print(f"  ⚠️  Would hit stop loss ({-triggers['stop_loss_percent']}%)")
            else:
                print(f"  ⏳ No trigger hit yet")
                
            position_data.append({
                'asset': asset,
                'pnl_pct': profit_loss_pct,
                'pnl_value': profit_loss_value,
                'current_value': current_value,
                'investment': investment_value
            })
            
        except Exception as e:
            print(f"  ⚠️  Could not fetch current price: {e}")
            
    # Overall portfolio summary
    print("\n" + "=" * 80)
    print("PORTFOLIO SUMMARY")
    print("=" * 80)
    print(f"Total Investment: ${total_investment_usd:.2f}")
    print(f"Current Value: ${total_current_value_usd:.2f}")
    
    if total_investment_usd > 0:
        total_pnl_pct = ((total_current_value_usd - total_investment_usd) / total_investment_usd) * 100
        total_pnl_value = total_current_value_usd - total_investment_usd
        print(f"Total P&L: {total_pnl_pct:+.2f}% (${total_pnl_value:+.2f})")
    
    return position_data

def suggest_optimal_triggers(position_data, current_triggers):
    """Suggest optimal trigger values based on position performance."""
    
    print("\n" + "=" * 80)
    print("TRIGGER OPTIMIZATION SUGGESTIONS")
    print("=" * 80)
    
    print("\n📊 CURRENT TRIGGERS:")
    print(f"  Buy Dip: {current_triggers['buy_dip_percent']}% drop from 7-day high")
    print(f"  First Profit Target: {current_triggers['profit_target_percent']}% gain (sell {current_triggers['profit_target_sell_percent']}%)")
    print(f"  Final Profit Target: {current_triggers['final_profit_target_percent']}% gain (sell remaining)")
    print(f"  Stop Loss: {current_triggers['stop_loss_percent']}% loss")
    
    if not position_data:
        print("\n⚠️  No position data to analyze")
        return
    
    # Calculate statistics
    pnl_values = [p['pnl_pct'] for p in position_data]
    profitable = [p for p in position_data if p['pnl_pct'] > 0]
    losing = [p for p in position_data if p['pnl_pct'] < 0]
    
    max_gain = max(pnl_values) if pnl_values else 0
    max_loss = min(pnl_values) if pnl_values else 0
    avg_pnl = sum(pnl_values) / len(pnl_values) if pnl_values else 0
    
    print(f"\n📈 POSITION STATISTICS:")
    print(f"  Total Positions: {len(position_data)}")
    print(f"  Profitable: {len(profitable)} ({len(profitable)/len(position_data)*100:.1f}%)")
    print(f"  Losing: {len(losing)} ({len(losing)/len(position_data)*100:.1f}%)")
    print(f"  Max Gain: {max_gain:+.2f}%")
    print(f"  Max Loss: {max_loss:+.2f}%")
    print(f"  Average P&L: {avg_pnl:+.2f}%")
    
    print("\n💡 RECOMMENDATIONS:")
    
    # Profit target suggestions
    if max_gain < current_triggers['profit_target_percent']:
        suggested_first = max(5, int(max_gain * 0.7))
        suggested_final = max(10, int(max_gain * 0.9))
        print(f"\n  🎯 PROFIT TARGETS - Too high! No positions have reached {current_triggers['profit_target_percent']}%")
        print(f"     Suggested First Target: {suggested_first}% (currently {current_triggers['profit_target_percent']}%)")
        print(f"     Suggested Final Target: {suggested_final}% (currently {current_triggers['final_profit_target_percent']}%)")
        print(f"     Rationale: Your max gain is {max_gain:.1f}%, so targets should be achievable")
    else:
        print(f"\n  ✅ PROFIT TARGETS - Current targets are achievable")
    
    # Stop loss suggestions
    if abs(max_loss) < current_triggers['stop_loss_percent']:
        print(f"\n  🛑 STOP LOSS - Could be tighter (currently {current_triggers['stop_loss_percent']}%)")
        suggested_stop = max(5, int(abs(max_loss) * 1.2))
        print(f"     Suggested: {suggested_stop}%")
        print(f"     Rationale: Your max loss is {max_loss:.1f}%, so you can protect capital better")
    elif abs(max_loss) > current_triggers['stop_loss_percent'] * 1.5:
        print(f"\n  ⚠️  STOP LOSS - Some positions fell below stop loss threshold!")
        print(f"     Current: {current_triggers['stop_loss_percent']}%")
        print(f"     Max Loss Seen: {abs(max_loss):.1f}%")
    else:
        print(f"\n  ✅ STOP LOSS - Current setting seems reasonable")
    
    # Buy dip suggestions
    print(f"\n  📉 BUY DIP - Currently {current_triggers['buy_dip_percent']}%")
    print(f"     Average P&L is {avg_pnl:+.2f}%, suggesting buy timing is {'good' if avg_pnl > 0 else 'could improve'}")
    if avg_pnl < -5:
        print(f"     Consider: Waiting for deeper dips (12-15%) or buying different assets")
    elif avg_pnl > 5:
        print(f"     Consider: Buying earlier dips (7-8%) to capture more gains")
    
    # Specific suggested config
    print("\n" + "=" * 80)
    print("SUGGESTED NEW CONFIGURATION:")
    print("=" * 80)
    
    new_triggers = {
        'profit_target_percent': max(10, min(20, int(max_gain * 0.7))) if max_gain > 0 else 15,
        'profit_target_sell_percent': 50,
        'final_profit_target_percent': max(20, min(35, int(max_gain * 0.9))) if max_gain > 0 else 30,
        'stop_loss_percent': max(8, min(12, int(abs(max_loss) * 1.2))) if max_loss < 0 else 10,
        'buy_dip_percent': 10 if avg_pnl >= 0 else 12
    }
    
    print(json.dumps(new_triggers, indent=2))
    
    print("\n⚠️  NOTE: These are suggestions based on current positions only.")
    print("    Consider market conditions and your risk tolerance before applying.")

def main():
    print("Loading configuration...")
    config = load_config()
    
    print("Analyzing positions (this may take a moment)...\n")
    position_data = analyze_position_performance(config)
    
    suggest_optimal_triggers(position_data, config['triggers'])
    
    print("\n" + "=" * 80)
    print("Analysis complete!")
    print("=" * 80)

if __name__ == "__main__":
    main()
