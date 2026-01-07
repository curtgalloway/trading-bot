#!/usr/bin/env python3
"""
Shared Coinbase API utilities
Provides common functions for authentication, API requests, and price fetching
"""
import json
import time
import secrets
import urllib.request
from urllib.error import HTTPError, URLError
from typing import Dict, Optional, List
import logging
import math

logger = logging.getLogger(__name__)

try:
    import jwt
except ImportError:
    jwt = None

BASE_URL = "https://api.coinbase.com"

# Rate limiting constants
MAX_REQUESTS_PER_SECOND = 10
REQUEST_INTERVAL = 1.0 / MAX_REQUESTS_PER_SECOND

# Retry constants
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1.0
MAX_RETRY_DELAY = 30.0

# Currency conversion constants
USD_TO_EUR_FALLBACK = 0.92
USDC_TO_EUR_FALLBACK = 0.92
USDT_TO_EUR_FALLBACK = 0.92
EUR_USD_RATE_CACHE_SECONDS = 3600  # Cache for 1 hour

class CoinbaseAPI:
    """Wrapper for Coinbase Advanced Trade API"""
    
    def __init__(self, credentials_file='cdp_api_key.json'):
        """Initialize with credentials from file"""
        self.credentials = self._load_credentials(credentials_file)
        self.private_key = self.credentials['privateKey']
        self.key_name = self.credentials['name']
        self.last_request_time = 0
        self.product_cache = {}  # Cache for product details
        self.eur_usd_rate = None  # Cached EUR/USD rate
        self.eur_usd_rate_timestamp = 0  # When rate was last fetched
    
    def _load_credentials(self, credentials_file):
        """Load API credentials from file"""
        with open(credentials_file, 'r') as f:
            return json.load(f)
    
    def _rate_limit(self):
        """Enforce rate limiting between requests"""
        elapsed = time.time() - self.last_request_time
        if elapsed < REQUEST_INTERVAL:
            time.sleep(REQUEST_INTERVAL - elapsed)
        self.last_request_time = time.time()
    
    def create_jwt(self, request_method: str, request_path: str) -> str:
        """
        Create JWT token for authentication
        
        Args:
            request_method: HTTP method (GET, POST, etc.)
            request_path: API endpoint path
            
        Returns:
            JWT token string
        """
        if jwt is None:
            raise ImportError("PyJWT library required. Install with: pip install PyJWT")
        
        uri = f"{request_method} api.coinbase.com{request_path}"
        
        token = jwt.encode(
            {
                "sub": self.key_name,
                "iss": "coinbase-cloud",
                "nbf": int(time.time()),
                "exp": int(time.time()) + 120,
                "uri": uri,
            },
            self.private_key,
            algorithm="ES256",
            headers={"kid": self.key_name, "nonce": secrets.token_hex(16)},
        )
        
        return token
    
    def api_request(self, method: str, path: str, data: Optional[Dict] = None) -> Optional[Dict]:
        """
        Make authenticated API request with retry logic
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: API endpoint path
            data: Optional request body data
            
        Returns:
            Response data as dict, or None on error
        """
        retry_delay = INITIAL_RETRY_DELAY
        
        for attempt in range(MAX_RETRIES):
            try:
                self._rate_limit()
                token = self.create_jwt(method, path)
                
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }
                
                if data:
                    req = urllib.request.Request(
                        f"{BASE_URL}{path}",
                        data=json.dumps(data).encode(),
                        headers=headers,
                        method=method
                    )
                else:
                    req = urllib.request.Request(
                        f"{BASE_URL}{path}",
                        headers=headers
                    )
                
                with urllib.request.urlopen(req, timeout=30) as response:
                    result = json.loads(response.read().decode())
                    logger.debug(f"API request successful: {method} {path}")
                    return result
                    
            except HTTPError as e:
                error_msg = e.read().decode()
                logger.error(f"HTTP Error {e.code} on {method} {path}: {error_msg}")
                
                # Don't retry on client errors (4xx)
                if 400 <= e.code < 500:
                    return None
                
                # Retry on server errors (5xx)
                if attempt < MAX_RETRIES - 1:
                    logger.warning(f"Retrying in {retry_delay}s... (attempt {attempt + 1}/{MAX_RETRIES})")
                    time.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, MAX_RETRY_DELAY)
                else:
                    return None
                    
            except URLError as e:
                logger.error(f"Network error on {method} {path}: {e}")
                if attempt < MAX_RETRIES - 1:
                    logger.warning(f"Retrying in {retry_delay}s... (attempt {attempt + 1}/{MAX_RETRIES})")
                    time.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, MAX_RETRY_DELAY)
                else:
                    return None
                    
            except Exception as e:
                logger.error(f"Unexpected error on {method} {path}: {e}")
                return None
        
        return None
    
    def get_price(self, asset: str, preferred_quotes: Optional[List[str]] = None) -> Optional[Dict]:
        """
        Get current price for an asset with retry logic
        
        Args:
            asset: Asset symbol (e.g., 'BTC', 'ETH')
            preferred_quotes: List of quote currencies to try in order
            
        Returns:
            Dict with price info or None
        """
        if preferred_quotes is None:
            # Prioritize USDC and EUR over USD - USD often requires specific account types
            # that may not be available for API trading
            preferred_quotes = ['USDC', 'EUR', 'USDT']
        
        for quote in preferred_quotes:
            pair = f"{asset}-{quote}"
            url = f"{BASE_URL}/api/v3/brokerage/market/products/{pair}/ticker"
            
            retry_delay = INITIAL_RETRY_DELAY
            
            for attempt in range(MAX_RETRIES):
                try:
                    req = urllib.request.Request(url)
                    with urllib.request.urlopen(req, timeout=10) as response:
                        data = json.loads(response.read().decode())
                        
                        price = data.get('price')
                        if not price:
                            price = data.get('best_ask') or data.get('best_bid')
                        
                        if price:
                            price = float(price)
                            if price > 0:
                                logger.debug(f"Got price for {pair}: {price}")
                                return {
                                    'price': price,
                                    'currency': quote,
                                    'best_bid': float(data.get('best_bid', price)),
                                    'best_ask': float(data.get('best_ask', price)),
                                    'pair': pair
                                }
                except (HTTPError, URLError) as e:
                    if attempt < MAX_RETRIES - 1:
                        logger.debug(f"Retrying price fetch for {pair} in {retry_delay}s...")
                        time.sleep(retry_delay)
                        retry_delay = min(retry_delay * 2, MAX_RETRY_DELAY)
                    else:
                        logger.debug(f"Failed to get price for {pair} after {MAX_RETRIES} attempts")
                        break
                except Exception as e:
                    logger.debug(f"Error fetching {pair}: {e}")
                    break
        
        logger.warning(f"Could not get price for {asset} with any quote currency")
        return None
    
    def get_accounts(self) -> List[Dict]:
        """
        Get all account balances
        
        Returns:
            List of account dictionaries
        """
        data = self.api_request("GET", "/api/v3/brokerage/accounts")
        if data:
            return data.get('accounts', [])
        return []
    
    def get_balance(self, currency: str) -> float:
        """
        Get balance for specific currency
        
        Args:
            currency: Currency symbol (e.g., 'EUR', 'USD')
            
        Returns:
            Available balance as float
        """
        accounts = self.get_accounts()
        for acc in accounts:
            if acc.get('currency') == currency:
                return float(acc.get('available_balance', {}).get('value', 0))
        return 0.0
    
    def place_order(self, product_id: str, side: str, amount: float, 
                   amount_type: str = 'base_size') -> Optional[Dict]:
        """
        Place a market order
        
        Args:
            product_id: Trading pair (e.g., 'BTC-EUR')
            side: 'BUY' or 'SELL'
            amount: Amount to trade
            amount_type: 'base_size' for base currency or 'quote_size' for quote currency
            
        Returns:
            Order response dict or None on error
        """
        order_data = {
            "client_order_id": f"{side.lower()}_{int(time.time())}",
            "product_id": product_id,
            "side": side,
            "order_configuration": {
                "market_market_ioc": {
                    amount_type: str(amount)
                }
            }
        }
        
        return self.api_request("POST", "/api/v3/brokerage/orders", order_data)

    def get_product(self, product_id: str) -> Optional[Dict]:
        """
        Get product details including precision requirements

        Args:
            product_id: Trading pair (e.g., 'BTC-EUR')

        Returns:
            Dict with product details or None on error
        """
        # Check cache first
        if product_id in self.product_cache:
            return self.product_cache[product_id]

        # Fetch from API
        result = self.api_request("GET", f"/api/v3/brokerage/market/products/{product_id}")
        if result:
            self.product_cache[product_id] = result
            return result
        return None

    def round_to_precision(self, amount: float, product_id: str, side: str = "BUY") -> float:
        """
        Round amount to the correct precision for a trading pair

        Args:
            amount: Amount to round
            product_id: Trading pair (e.g., 'BTC-EUR')
            side: 'BUY' or 'SELL' - SELL orders round down to avoid insufficient balance

        Returns:
            Rounded amount
        """
        product = self.get_product(product_id)
        if not product:
            # Fallback to 8 decimals if we can't get product info
            logger.warning(f"Could not get product details for {product_id}, using 8 decimal precision")
            if side == "SELL":
                return math.floor(amount * 1e8) / 1e8
            return round(amount, 8)

        # Log the full product details to debug
        logger.info(f"Product details for {product_id}: base_increment={product.get('base_increment')}, base_min_size={product.get('base_min_size')}, base_max_size={product.get('base_max_size')}")

        # Get base_increment from product details
        base_increment = product.get('base_increment', '0.00000001')

        # Count decimal places in base_increment
        if '.' in base_increment:
            decimals = len(base_increment.split('.')[1].rstrip('0'))
        else:
            decimals = 0

        # For SELL orders, always round DOWN to avoid selling more than we have
        # For BUY orders, use standard rounding
        if side == "SELL":
            multiplier = 10 ** decimals
            rounded = math.floor(amount * multiplier) / multiplier
        else:
            rounded = round(amount, decimals)

        logger.info(f"Rounded {amount} to {rounded} ({decimals} decimals, side={side}, base_increment={base_increment}) for {product_id}")
        return rounded

    def get_eur_usd_rate(self) -> float:
        """
        Get current EUR/USD exchange rate with caching
        
        Returns:
            EUR/USD rate as float
        """
        # Check if cached rate is still valid
        if self.eur_usd_rate is not None:
            elapsed = time.time() - self.eur_usd_rate_timestamp
            if elapsed < EUR_USD_RATE_CACHE_SECONDS:
                logger.debug(f"Using cached EUR/USD rate: {self.eur_usd_rate:.4f} (age: {elapsed:.0f}s)")
                return self.eur_usd_rate
        
        # Fetch fresh rate
        try:
            price_data = self.get_price('USDC', preferred_quotes=['EUR'])
            if price_data and price_data['currency'] == 'EUR':
                rate = price_data['price']
                self.eur_usd_rate = rate
                self.eur_usd_rate_timestamp = time.time()
                logger.info(f"Fetched fresh EUR/USD rate: {rate:.4f}")
                return rate
        except Exception as e:
            logger.warning(f"Failed to fetch EUR/USD rate: {e}, using fallback {USD_TO_EUR_FALLBACK}")
        
        # Use fallback if fetch failed
        return USD_TO_EUR_FALLBACK

    def convert_to_eur(self, amount: float, currency: str) -> float:
        """
        Convert an amount from any currency to EUR
        
        Args:
            amount: Amount to convert
            currency: Source currency (EUR, USD, USDC, USDT, etc.)
            
        Returns:
            Amount in EUR
        """
        if currency == 'EUR':
            return amount
        elif currency in ['USD', 'USDC', 'USDT']:
            rate = self.get_eur_usd_rate()
            return amount * rate
        else:
            logger.warning(f"Unknown currency {currency}, assuming EUR")
            return amount


def get_price_simple(product_id: str) -> Optional[Dict]:
    """
    Get price for a specific trading pair without authentication
    
    Args:
        product_id: Trading pair (e.g., 'BTC-EUR')
        
    Returns:
        Dict with price data or None on error
    """
    url = f"{BASE_URL}/api/v3/brokerage/market/products/{product_id}/ticker"
    
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode())
            return data
    except Exception as e:
        print(f"Error fetching price: {e}")
        return None


def validate_config(config: Dict) -> bool:
    """
    Validate trading configuration structure
    
    Args:
        config: Configuration dictionary
        
    Returns:
        True if valid, raises ValueError if invalid
    """
    required_fields = [
        'trading_budget_eur',
        'minimum_balance_eur',
        'check_interval_minutes',
        'dry_run',
        'triggers',
        'fees',
        'tracked_assets',
        'position_tracking'
    ]
    
    for field in required_fields:
        if field not in config:
            raise ValueError(f"Missing required config field: {field}")
    
    # Validate triggers
    required_triggers = [
        'profit_target_percent',
        'profit_target_sell_percent',
        'final_profit_target_percent',
        'stop_loss_percent'
    ]
    for trigger in required_triggers:
        if trigger not in config['triggers']:
            raise ValueError(f"Missing required trigger: {trigger}")
    
    # Validate fees
    if 'taker_fee_rate' not in config['fees']:
        raise ValueError("Missing taker_fee_rate in fees")
    
    # Validate numeric values
    if config['trading_budget_eur'] <= 0:
        raise ValueError("trading_budget_eur must be positive")
    
    if config['minimum_balance_eur'] < 0:
        raise ValueError("minimum_balance_eur cannot be negative")
    
    if config['check_interval_minutes'] <= 0:
        raise ValueError("check_interval_minutes must be positive")
    
    # Validate types
    if not isinstance(config['dry_run'], bool):
        raise ValueError("dry_run must be a boolean")
    
    if not isinstance(config['tracked_assets'], list):
        raise ValueError("tracked_assets must be a list")
    
    if not isinstance(config['position_tracking'], dict):
        raise ValueError("position_tracking must be a dictionary")
    
    logger.info("Config validation passed")
    return True
