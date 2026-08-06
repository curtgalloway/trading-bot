#!/usr/bin/env python3
"""
Store historical price data for cryptocurrencies in SQLite
"""
import sqlite3
import requests
from datetime import datetime
import logging
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class PriceHistoryDB:
    def __init__(self, db_path='price_history.db'):
        self.db_path = db_path
        
    def create_tables(self):
        """Create tables for storing price history"""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timestamp INTEGER NOT NULL,
            datetime TEXT NOT NULL,
            price REAL NOT NULL,
            market_cap REAL,
            volume_24h REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(symbol, timestamp)
        );
        
        CREATE INDEX IF NOT EXISTS idx_symbol_timestamp ON price_history(symbol, timestamp);
        CREATE INDEX IF NOT EXISTS idx_datetime ON price_history(datetime);
        """
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.executescript(create_table_sql)
            conn.commit()
            logger.info(f"Database initialized at {self.db_path}")
            cursor.close()
            conn.close()
        except Exception as e:
            logger.error(f"Error creating tables: {e}")
            raise
    
    def fetch_coingecko_data(self, coin_id, days=7):
        """Fetch historical price data from CoinGecko"""
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
        params = {
            'vs_currency': 'usd',
            'days': days,
            'interval': 'daily'
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            logger.info(f"Fetched {len(data['prices'])} data points for {coin_id}")
            return data
        except Exception as e:
            logger.error(f"Error fetching data for {coin_id}: {e}")
            raise
    
    def store_price_data(self, symbol, data):
        """Store price data in the database"""
        insert_sql = """
        INSERT OR REPLACE INTO price_history (symbol, timestamp, datetime, price, market_cap, volume_24h)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            records = []
            for i in range(len(data['prices'])):
                timestamp_ms = data['prices'][i][0]
                price = data['prices'][i][1]
                market_cap = data['market_caps'][i][1] if i < len(data['market_caps']) else None
                volume = data['total_volumes'][i][1] if i < len(data['total_volumes']) else None
                
                dt = datetime.fromtimestamp(timestamp_ms / 1000).isoformat()
                records.append((symbol, timestamp_ms, dt, price, market_cap, volume))
            
            cursor.executemany(insert_sql, records)
            conn.commit()
            logger.info(f"Stored {len(records)} records for {symbol}")
            
            cursor.close()
            conn.close()
        except Exception as e:
            logger.error(f"Error storing data for {symbol}: {e}")
            raise
    
    def get_latest_prices(self, symbol=None, limit=10):
        """Retrieve latest prices from the database"""
        query = """
        SELECT symbol, datetime, price, market_cap, volume_24h
        FROM price_history
        """
        params = []
        if symbol:
            query += " WHERE symbol = ?"
            params.append(symbol)
        query += " ORDER BY datetime DESC LIMIT ?"
        params.append(limit)
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(query, params)
            results = cursor.fetchall()
            cursor.close()
            conn.close()
            return results
        except Exception as e:
            logger.error(f"Error retrieving data: {e}")
            raise
    
    def get_price_stats(self, symbol, days=7):
        """Get price statistics for a symbol"""
        query = """
        SELECT 
            symbol,
            COUNT(*) as data_points,
            MIN(price) as min_price,
            MAX(price) as max_price,
            AVG(price) as avg_price,
            MIN(datetime) as from_date,
            MAX(datetime) as to_date
        FROM price_history
        WHERE symbol = ?
        AND datetime >= datetime('now', '-' || ? || ' days')
        GROUP BY symbol
        """
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(query, (symbol, days))
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            return result
        except Exception as e:
            logger.error(f"Error retrieving stats: {e}")
            raise


def main():
    # Initialize database connection
    db = PriceHistoryDB('price_history.db')
    
    # Create tables
    logger.info("Setting up database...")
    db.create_tables()
    
    # Fetch and store data for BTC and ETH
    coins = [
        ('bitcoin', 'BTC'),
        ('ethereum', 'ETH')
    ]
    
    for coin_id, symbol in coins:
        logger.info(f"Processing {symbol}...")
        data = db.fetch_coingecko_data(coin_id, days=30)
        db.store_price_data(symbol, data)
    
    # Display some results
    print("\n" + "="*70)
    print("LATEST BTC PRICES")
    print("="*70)
    btc_prices = db.get_latest_prices('BTC', limit=5)
    for row in btc_prices:
        print(f"{row[0]}: {row[1][:19]} - ${row[2]:,.2f} | MCap: ${row[3]/1e9:.2f}B | Vol: ${row[4]/1e9:.2f}B")
    
    print("\n" + "="*70)
    print("LATEST ETH PRICES")
    print("="*70)
    eth_prices = db.get_latest_prices('ETH', limit=5)
    for row in eth_prices:
        print(f"{row[0]}: {row[1][:19]} - ${row[2]:,.2f} | MCap: ${row[3]/1e9:.2f}B | Vol: ${row[4]/1e9:.2f}B")
    
    print("\n" + "="*70)
    print("30-DAY STATISTICS")
    print("="*70)
    for coin_id, symbol in coins:
        stats = db.get_price_stats(symbol, days=30)
        if stats:
            print(f"\n{stats[0]}:")
            print(f"  Data points: {stats[1]}")
            print(f"  Price range: ${stats[2]:,.2f} - ${stats[3]:,.2f}")
            print(f"  Average: ${stats[4]:,.2f}")
            print(f"  Period: {stats[5][:10]} to {stats[6][:10]}")
    
    print("\n" + "="*70)
    print(f"✓ Database saved to: {os.path.abspath(db.db_path)}")
    print("="*70)


if __name__ == '__main__':
    main()
