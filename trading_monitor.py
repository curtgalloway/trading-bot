#!/usr/bin/env python3
"""
Crypto Trading Monitor with Trigger-based Buy/Sell
Monitors portfolio and executes trades based on price triggers
"""
import json
import time
import logging
from datetime import datetime
from typing import Dict, Optional
from coinbase_api import CoinbaseAPI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constants
USD_TO_EUR_FALLBACK = 0.92  # Fallback conversion rate
USDC_TO_EUR_FALLBACK = 0.92
USDT_TO_EUR_FALLBACK = 0.92

class TradingMonitor:
    def __init__(self, config_file='trading_config.json'):
        self.config = self.load_config(config_file)
        self.config_file = config_file
        self.current_eur_balance = self.config['trading_budget_eur']
        self.api = CoinbaseAPI()
        self.eur_usd_rate = None
        logger.info(f"Trading Monitor initialized - Mode: {'DRY RUN' if self.config['dry_run'] else 'LIVE TRADING'}")
        
    def load_config(self, config_file):
        """Load trading configuration"""
        with open(config_file, 'r') as f:
            return json.load(f)
    
    def save_config(self):
        """Save updated configuration (for position tracking)"""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def get_price(self, product_id):
        """Get current price for a trading pair"""
        return self.api.get_price(product_id)
    
    def get_accounts(self):
        """Get all account balances"""
        return self.api.get_accounts()
    
    def get_eur_balance(self):
        """Get current EUR balance"""
        return self.api.get_balance('EUR')
    
    def get_eur_usd_rate(self):
        """Get current EUR/USD exchange rate"""
        try:
            # Get USD-EUR price
            price_data = self.api.get_price('USDC', preferred_quotes=['EUR'])
            if price_data and price_data['currency'] == 'EUR':
                rate = price_data['price']
                logger.info(f"Fetched EUR/USD rate: {rate:.4f}")
                return rate
        except Exception as e:
            logger.warning(f"Failed to fetch EUR/USD rate: {e}, using fallback {USD_TO_EUR_FALLBACK}")
        
        return USD_TO_EUR_FALLBACK
    
    def get_holdings(self):
        """Get non-zero holdings"""
        accounts = self.get_accounts()
        holdings = {}
        
        for acc in accounts:
            currency = acc.get('currency')
            balance = float(acc.get('available_balance', {}).get('value', 0))
            
            if balance > 0 and currency in self.config['tracked_assets']:
                holdings[currency] = balance
        
        return holdings
    
    def calculate_position_value(self, asset, amount, current_price_data):
        """Calculate current value of position in EUR"""
        if not current_price_data:
            return 0
        
        price = current_price_data['price']
        currency = current_price_data['currency']
        
        value = amount * price
        
        # Convert to EUR if needed
        if currency == 'EUR':
            return value
        elif currency == 'USD':
            if self.eur_usd_rate is None:
                self.eur_usd_rate = self.get_eur_usd_rate()
            value = value * self.eur_usd_rate
        elif currency in ['USDT', 'USDC']:
            if self.eur_usd_rate is None:
                self.eur_usd_rate = self.get_eur_usd_rate()
            value = value * self.eur_usd_rate
        
        return value
    
    def check_triggers(self, asset, amount, current_price_data):
        """Check if any triggers are hit for this asset"""
        if not current_price_data:
            return None
        
        triggers = self.config['triggers']
        positions = self.config['position_tracking']
        
        # If we don't have entry price, record current as baseline
        if asset not in positions:
            positions[asset] = {
                'entry_price': current_price_data['price'],
                'entry_currency': current_price_data['currency'],
                'amount': amount,
                'entry_time': datetime.now().isoformat(),
                'total_sold': 0.0
            }
            self.save_config()
            logger.info(f"Tracked new position: {asset} @ {current_price_data['price']} {current_price_data['currency']}, amount: {amount}")
            print(f"  📝 Tracked new position: {asset} @ {current_price_data['price']} {current_price_data['currency']}")
            return None
        
        entry_price = positions[asset]['entry_price']
        current_price = current_price_data['price']
        
        # Calculate percentage change
        pct_change = ((current_price - entry_price) / entry_price) * 100
        
        # Check final profit target (sell all at +50%) - check this FIRST
        if pct_change >= triggers['final_profit_target_percent']:
            return {
                'action': 'SELL',
                'reason': f'Final profit target hit: +{pct_change:.2f}%',
                'amount': amount,
                'price': current_price_data,
                'is_full_exit': True
            }
        
        # Check profit target (sell 50% at +25%)
        # Only trigger if we haven't already sold partial position
        total_sold = positions[asset].get('total_sold', 0.0)
        original_amount = positions[asset].get('amount', amount)
        
        if pct_change >= triggers['profit_target_percent'] and total_sold == 0:
            sell_amount = original_amount * (triggers['profit_target_sell_percent'] / 100)
            return {
                'action': 'SELL',
                'reason': f'Profit target hit: +{pct_change:.2f}%',
                'amount': sell_amount,
                'price': current_price_data,
                'is_full_exit': False
            }
        
        # Check stop loss (sell all at -15%)
        if pct_change <= -triggers['stop_loss_percent']:
            return {
                'action': 'SELL',
                'reason': f'Stop loss hit: {pct_change:.2f}%',
                'amount': amount,
                'price': current_price_data,
                'is_full_exit': True
            }
        
        return None
    
    def execute_trade(self, action, asset, amount, price_data, is_full_exit=True):
        """Execute a trade (or simulate in dry-run mode)"""
        currency = price_data['currency']
        price = price_data['price']
        value = amount * price
        
        # Convert to EUR if needed
        if currency == 'EUR':
            value_eur = value
        elif currency in ['USD', 'USDC', 'USDT']:
            if self.eur_usd_rate is None:
                self.eur_usd_rate = self.get_eur_usd_rate()
            value_eur = value * self.eur_usd_rate
        else:
            value_eur = value
        
        # Calculate fees
        fee = value_eur * self.config['fees']['taker_fee_rate']
        
        if action == 'SELL':
            net_proceeds = value_eur - fee
            
            # Calculate P&L if we have position tracking
            profit_loss = 0
            if asset in self.config['position_tracking']:
                pos = self.config['position_tracking'][asset]
                entry_price = pos['entry_price']
                entry_currency = pos['entry_currency']
                
                # Calculate cost basis for this sale
                cost_basis_per_unit = entry_price
                if entry_currency != 'EUR' and entry_currency in ['USD', 'USDC', 'USDT']:
                    cost_basis_per_unit = entry_price * self.eur_usd_rate
                
                cost_basis = amount * cost_basis_per_unit
                profit_loss = net_proceeds - cost_basis
            
            if self.config['dry_run']:
                print(f"  🔴 [DRY RUN] SELL {amount:.8f} {asset}")
                print(f"     Price: {price:.8f} {currency}")
                print(f"     Gross: €{value_eur:.2f}")
                print(f"     Fee: €{fee:.2f}")
                print(f"     Net: €{net_proceeds:.2f}")
                if profit_loss != 0:
                    print(f"     P&L: €{profit_loss:+.2f}")
                
                logger.info(f"[DRY RUN] SELL {amount:.8f} {asset} @ {price:.8f} {currency}, Net: €{net_proceeds:.2f}, P&L: €{profit_loss:+.2f}")
                
                # Update tracking
                self.current_eur_balance += net_proceeds
                if asset in self.config['position_tracking']:
                    if is_full_exit:
                        # Remove position entirely
                        del self.config['position_tracking'][asset]
                        logger.info(f"Position closed: {asset}")
                    else:
                        # Update partial sell tracking
                        pos = self.config['position_tracking'][asset]
                        pos['total_sold'] = pos.get('total_sold', 0.0) + amount
                        logger.info(f"Partial sell: {asset}, sold {amount:.8f}, total sold: {pos['total_sold']:.8f}")
                    self.save_config()
            else:
                # Actual sell order
                product_id = f"{asset}-{currency}"
                logger.info(f"Placing SELL order: {amount:.8f} {asset} on {product_id}")
                result = self.api.place_order(product_id, "SELL", amount, 'base_size')
                if result:
                    print(f"  ✅ SELL order placed: {result}")
                    logger.info(f"SELL order success: {result}")
                    self.current_eur_balance += net_proceeds
                    
                    # Update position tracking
                    if asset in self.config['position_tracking']:
                        if is_full_exit:
                            del self.config['position_tracking'][asset]
                        else:
                            pos = self.config['position_tracking'][asset]
                            pos['total_sold'] = pos.get('total_sold', 0.0) + amount
                        self.save_config()
                else:
                    print(f"  ❌ SELL order failed")
                    logger.error(f"SELL order failed for {asset}")
        
        elif action == 'BUY':
            total_cost = value_eur + fee
            
            if self.config['dry_run']:
                print(f"  🟢 [DRY RUN] BUY {amount:.8f} {asset}")
                print(f"     Price: {price:.8f} {currency}")
                print(f"     Cost: €{value_eur:.2f}")
                print(f"     Fee: €{fee:.2f}")
                print(f"     Total: €{total_cost:.2f}")
                
                logger.info(f"[DRY RUN] BUY {amount:.8f} {asset} @ {price:.8f} {currency}, Total: €{total_cost:.2f}")
                
                # Update tracking
                self.current_eur_balance -= total_cost
                self.config['position_tracking'][asset] = {
                    'entry_price': price,
                    'entry_currency': currency,
                    'amount': amount,
                    'entry_time': datetime.now().isoformat(),
                    'total_sold': 0.0
                }
                self.save_config()
            else:
                # Actual buy order
                product_id = f"{asset}-{currency}"
                logger.info(f"Placing BUY order: {amount:.8f} {asset} on {product_id}")
                result = self.api.place_order(product_id, "BUY", value_eur, 'quote_size')
                if result:
                    print(f"  ✅ BUY order placed: {result}")
                    logger.info(f"BUY order success: {result}")
                    self.current_eur_balance -= total_cost
                    
                    # Update position tracking
                    self.config['position_tracking'][asset] = {
                        'entry_price': price,
                        'entry_currency': currency,
                        'amount': amount,
                        'entry_time': datetime.now().isoformat(),
                        'total_sold': 0.0
                    }
                    self.save_config()
                else:
                    print(f"  ❌ BUY order failed")
                    logger.error(f"BUY order failed for {asset}")
    
    def monitor_cycle(self):
        """Run one monitoring cycle"""
        print("\n" + "="*70)
        print(f"🔍 Monitoring Cycle - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)
        
        # Check EUR balance
        actual_eur = self.get_eur_balance()
        print(f"\n💶 Actual EUR Balance: €{actual_eur:.2f}")
        print(f"💰 Trading Budget Tracker: €{self.current_eur_balance:.2f}")
        
        # Safety check - stop if trading budget nearly depleted
        if self.current_eur_balance < self.config['minimum_balance_eur']:
            print(f"\n⚠️  TRADING HALTED: Budget depleted (€{self.current_eur_balance:.2f} < €{self.config['minimum_balance_eur']})")
            print(f"   You've lost most of your €{self.config['trading_budget_eur']} initial budget.")
            return False
        
        # Get holdings
        holdings = self.get_holdings()
        print(f"\n📊 Monitoring {len(holdings)} assets...")
        
        # Check each holding for triggers
        for asset, amount in holdings.items():
            print(f"\n  {asset}: {amount:.8f}")
            
            price_data = self.get_price(asset)
            if price_data:
                value_eur = self.calculate_position_value(asset, amount, price_data)
                print(f"    Pair: {price_data['pair']}")
                print(f"    Price: {price_data['price']:.8f} {price_data['currency']}")
                print(f"    Value: €{value_eur:.2f}")
                
                # Check triggers
                trigger = self.check_triggers(asset, amount, price_data)
                if trigger:
                    print(f"    🎯 TRIGGER: {trigger['reason']}")
                    is_full_exit = trigger.get('is_full_exit', True)
                    self.execute_trade(trigger['action'], asset, trigger['amount'], trigger['price'], is_full_exit)
            else:
                print(f"    ⚠️  Price not available (no trading pairs found)")
        
        print(f"\n💰 Updated Trading Budget: €{self.current_eur_balance:.2f}")
        print("="*70)
        
        return True
    
    def run(self):
        """Main monitoring loop"""
        print("\n🚀 Crypto Trading Monitor Started")
        print(f"Mode: {'DRY RUN' if self.config['dry_run'] else 'LIVE TRADING'}")
        print(f"Check Interval: {self.config['check_interval_minutes']} minutes")
        print(f"Trading Budget: €{self.config['trading_budget_eur']:.2f}")
        print(f"Minimum Balance: €{self.config['minimum_balance_eur']:.2f}")
        print("\nPress Ctrl+C to stop\n")
        
        try:
            while True:
                should_continue = self.monitor_cycle()
                
                if not should_continue:
                    print("\n⛔ Trading stopped due to insufficient balance")
                    break
                
                # Wait for next cycle
                sleep_seconds = self.config['check_interval_minutes'] * 60
                print(f"\n😴 Sleeping for {self.config['check_interval_minutes']} minutes...")
                time.sleep(sleep_seconds)
                
        except KeyboardInterrupt:
            print("\n\n⏹️  Monitor stopped by user")
            print(f"Final Trading Budget: €{self.current_eur_balance:.2f}")

if __name__ == "__main__":
    monitor = TradingMonitor()
    monitor.run()
