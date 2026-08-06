#!/usr/bin/env python3
"""Query the price history database"""
import sqlite3
import sys

db_path = 'price_history.db'

def query_prices(symbol, limit=10):
    """Get recent prices for a symbol"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT datetime, price, market_cap, volume_24h FROM price_history WHERE symbol = ? ORDER BY datetime DESC LIMIT ?",
        (symbol, limit)
    )
    results = cursor.fetchall()
    conn.close()
    
    print(f"\nLatest {limit} prices for {symbol}:")
    print("="*70)
    for row in results:
        print(f"{row[0][:19]} | ${row[1]:,.2f} | MCap: ${row[2]/1e9:.2f}B | Vol: ${row[3]/1e9:.2f}B")

if __name__ == '__main__':
    symbol = sys.argv[1] if len(sys.argv) > 1 else 'BTC'
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    query_prices(symbol, limit)
