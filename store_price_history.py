#!/usr/bin/env python3
"""
Store historical price data for cryptocurrencies in PostgreSQL
"""
import psycopg2
import requests
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class PriceHistoryDB:
    def __init__(self, dbname='trading_bot', user=None, password='', host='', port=5432):
        # Use peer authentication (Unix socket) by not specifying host/user
        self.conn_params = {
            'dbname': dbname
        }
        if user:
            self.conn_params['user'] = user
        if password:
            self.conn_params['password'] = password
        if host:
            self.conn_params['host'] = host
            self.conn_params['port'] = port
        
    def create_database(self):
        """Create the database if it doesn't exist"""
        try:
            # Connect to default postgres database using peer authentication
            conn = psycopg2.connect(dbname='postgres')
            conn.autocommit = True
            cursor = conn.cursor()
            
            # Check if database exists
            cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{self.conn_params['dbname']}'")
            exists = cursor.fetchone()
            
            if not exists:
                cursor.execute(f"CREATE DATABASE {self.conn_params['dbname']}")
                logger.info(f"Database '{self.conn_params['dbname']}' created successfully")
            else:
                logger.info(f"Database '{self.conn_params['dbname']}' already exists")
                
            cursor.close()
            conn.close()
        except Exception as e:
            logger.error(f"Error creating database: {e}")
            raise
    
    def create_tables(self):
        """Create tables for storing price history"""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS price_history (
            id SERIAL PRIMARY KEY,
            symbol VARCHAR(10) NOT NULL,
            timestamp BIGINT NOT NULL,
            datetime TIMESTAMP NOT NULL,
            price DECIMAL(20, 8) NOT NULL,
            market_cap DECIMAL(30, 2),
            volume_24h DECIMAL(30, 2),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(symbol, timestamp)
        );
        
        CREATE INDEX IF NOT EXISTS idx_symbol_timestamp ON price_history(symbol, timestamp);
        CREATE INDEX IF NOT EXISTS idx_datetime ON price_history(datetime);
        """
        
        try:
            conn = psycopg2.connect(**self.conn_params)
            cursor = conn.cursor()
            cursor.execute(create_table_sql)
            conn.commit()
            logger.info("Tables created successfully")
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
        INSERT INTO price_history (symbol, timestamp, datetime, price, market_cap, volume_24h)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (symbol, timestamp) DO UPDATE SET
            price = EXCLUDED.price,
            market_cap = EXCLUDED.market_cap,
            volume_24h = EXCLUDED.volume_24h
        """
        
        try:
            conn = psycopg2.connect(**self.conn_params)
            cursor = conn.cursor()
            
            records = []
            for i in range(len(data['prices'])):
                timestamp_ms = data['prices'][i][0]
                price = data['prices'][i][1]
                market_cap = data['market_caps'][i][1] if i < len(data['market_caps']) else None
                volume = data['total_volumes'][i][1] if i < len(data['total_volumes']) else None
                
                dt = datetime.fromtimestamp(timestamp_ms / 1000)
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
        if symbol:
            query += f" WHERE symbol = '{symbol}'"
        query += " ORDER BY datetime DESC LIMIT %s"
        
        try:
            conn = psycopg2.connect(**self.conn_params)
            cursor = conn.cursor()
            cursor.execute(query, (limit,))
            results = cursor.fetchall()
            cursor.close()
            conn.close()
            return results
        except Exception as e:
            logger.error(f"Error retrieving data: {e}")
            raise


def main():
    # Initialize database connection
    db = PriceHistoryDB()
    
    # Create database and tables
    logger.info("Setting up database...")
    db.create_database()
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
    logger.info("\nLatest BTC prices:")
    btc_prices = db.get_latest_prices('BTC', limit=5)
    for row in btc_prices:
        print(f"{row[0]}: {row[1]} - ${row[2]:,.2f}")
    
    logger.info("\nLatest ETH prices:")
    eth_prices = db.get_latest_prices('ETH', limit=5)
    for row in eth_prices:
        print(f"{row[0]}: {row[1]} - ${row[2]:,.2f}")


if __name__ == '__main__':
    main()
