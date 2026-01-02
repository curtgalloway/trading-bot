#!/usr/bin/env python3
"""
Simple script to get BTC price in EUR using Coinbase Advanced Trade API
"""
from coinbase_api import get_price_simple

def get_btc_eur_price():
    data = get_price_simple('BTC-EUR')
    
    if not data:
        return None
    
    best_bid = float(data['best_bid'])
    best_ask = float(data['best_ask'])
    mid_price = (best_bid + best_ask) / 2
    
    print(f"BTC/EUR Price:")
    print(f"  Best Bid: €{best_bid:,.2f}")
    print(f"  Best Ask: €{best_ask:,.2f}")
    print(f"  Mid Price: €{mid_price:,.2f}")
    
    return mid_price

if __name__ == "__main__":
    get_btc_eur_price()
