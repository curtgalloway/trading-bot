#!/usr/bin/env python3
"""
Crypto Trading Monitor with Trigger-based Buy/Sell
Monitors portfolio and executes trades based on price triggers
"""
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
from coinbase_api import CoinbaseAPI, validate_config

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

class TradingMonitor:
    def __init__(self, config_file='trading_config.json'):
        self.config = self.load_config(config_file)
        self.config_file = config_file
        self.current_eur_balance = self.config['trading_budget_eur']
        self.api = CoinbaseAPI()
        logger.info(f"Trading Monitor initialized - Mode: {'DRY RUN' if self.config['dry_run'] else 'LIVE TRADING'}")

        # Initialize buy-related config structures
        if 'price_history' not in self.config:
            self.config['price_history'] = {}
        if 'sold_positions' not in self.config:
            self.config['sold_positions'] = {}
            self.save_config()

        # Clean up expired data on startup
        self.cleanup_price_history()
        self.cleanup_sold_positions()
        
    def load_config(self, config_file):
        """Load and validate trading configuration"""
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            validate_config(config)
            return config
        except FileNotFoundError:
            logger.error(f"Configuration file {config_file} not found")
            raise
        except ValueError as e:
            logger.error(f"Invalid configuration: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in configuration file: {e}")
            raise
    
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
        return self.api.convert_to_eur(value, currency)
    
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
        entry_currency = positions[asset]['entry_currency']
        current_price = current_price_data['price']
        current_currency = current_price_data['currency']
        
        # Calculate percentage change - convert to same currency (EUR) for accurate comparison
        entry_price_eur = self.api.convert_to_eur(entry_price, entry_currency)
        current_price_eur = self.api.convert_to_eur(current_price, current_currency)
        pct_change = ((current_price_eur - entry_price_eur) / entry_price_eur) * 100
        
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

    def track_price_history(self, asset, price_data):
        """Track current price for rolling 7-day window"""
        # Initialize price_history if needed
        if 'price_history' not in self.config:
            self.config['price_history'] = {}

        if asset not in self.config['price_history']:
            self.config['price_history'][asset] = []

        # Add new price point
        price_entry = {
            'price': price_data['price'],
            'currency': price_data['currency'],
            'timestamp': datetime.now().isoformat()
        }
        self.config['price_history'][asset].append(price_entry)

        # Clean up old entries
        self.cleanup_price_history()
        self.save_config()
        logger.debug(f"Tracked price for {asset}: {price_data['price']} {price_data['currency']}")

    def cleanup_price_history(self):
        """Remove price entries older than 7 days"""
        if 'price_history' not in self.config:
            return

        cutoff = datetime.now() - timedelta(days=7)

        for asset in list(self.config['price_history'].keys()):
            # Filter entries newer than cutoff
            self.config['price_history'][asset] = [
                entry for entry in self.config['price_history'][asset]
                if datetime.fromisoformat(entry['timestamp']) > cutoff
            ]

            # Remove asset if no entries remain
            if not self.config['price_history'][asset]:
                del self.config['price_history'][asset]

        logger.debug(f"Cleaned up price history, {len(self.config['price_history'])} assets remain")

    def record_sold_position(self, asset, price_data, amount):
        """Track a sold position for re-entry logic"""
        # Initialize sold_positions if needed
        if 'sold_positions' not in self.config:
            self.config['sold_positions'] = {}

        sale_timestamp = datetime.now()
        expires_at = sale_timestamp + timedelta(days=30)

        self.config['sold_positions'][asset] = {
            'sale_price': price_data['price'],
            'sale_currency': price_data['currency'],
            'sale_timestamp': sale_timestamp.isoformat(),
            'sale_amount': amount,
            'expires_at': expires_at.isoformat()
        }

        self.save_config()
        logger.info(f"Recorded sold position: {asset} @ {price_data['price']} {price_data['currency']}, expires {expires_at.date()}")

    def cleanup_sold_positions(self):
        """Remove expired sold positions (older than 30 days)"""
        if 'sold_positions' not in self.config:
            return

        now = datetime.now()
        expired = []

        for asset, pos in list(self.config['sold_positions'].items()):
            expires_at = datetime.fromisoformat(pos['expires_at'])
            if expires_at < now:
                expired.append(asset)
                del self.config['sold_positions'][asset]

        if expired:
            self.save_config()
            logger.info(f"Removed {len(expired)} expired sold positions: {', '.join(expired)}")

    def get_7day_high(self, asset):
        """Get highest price in the last 7 days for an asset"""
        if 'price_history' not in self.config:
            return None

        if asset not in self.config['price_history']:
            return None

        history = self.config['price_history'][asset]
        if not history:
            return None

        # Convert all prices to EUR for comparison using centralized function
        max_price_eur = 0
        for entry in history:
            price_eur = self.api.convert_to_eur(entry['price'], entry['currency'])
            max_price_eur = max(max_price_eur, price_eur)

        return max_price_eur if max_price_eur > 0 else None

    def check_buy_triggers(self):
        """Check for buy opportunities (dip buying and re-entry)"""
        buy_opportunities = []

        # Get current holdings to avoid duplicate buys
        holdings = self.get_holdings()

        # Check buy-the-dip for configured assets (BTC, ETH)
        buy_assets = self.config['triggers'].get('buy_assets', [])
        for asset in buy_assets:
            # Skip if we already hold this asset (buy-the-dip only)
            if asset in holdings:
                continue

            # Get current price
            price_data = self.get_price(asset)
            if not price_data:
                continue

            # Get 7-day high
            seven_day_high = self.get_7day_high(asset)
            if seven_day_high is None:
                logger.debug(f"No 7-day high for {asset}, skipping buy-the-dip")
                continue

            # Convert current price to EUR for comparison
            current_price_eur = self.api.convert_to_eur(price_data['price'], price_data['currency'])

            # Calculate dip percentage
            dip_percent = ((current_price_eur - seven_day_high) / seven_day_high) * 100

            # Trigger if dip exceeds configured threshold
            if dip_percent <= -self.config["triggers"]["buy_dip_percent"]:
                buy_opportunities.append({
                    'action': 'BUY',
                    'asset': asset,
                    'reason': f'Buy-the-dip: {dip_percent:.2f}% from 7-day high',
                    'amount_eur': self.config['triggers']['buy_amount_eur'],
                    'price': price_data
                })
                logger.info(f"Buy-the-dip trigger: {asset} at {dip_percent:.2f}% from 7-day high")

        # Check re-entry opportunities for sold positions
        if 'sold_positions' in self.config:
            for asset, sold_pos in self.config['sold_positions'].items():
                # Get current price
                price_data = self.get_price(asset)
                if not price_data:
                    continue

                # Convert both to EUR for comparison using centralized function
                sale_price_eur = self.api.convert_to_eur(sold_pos['sale_price'], sold_pos['sale_currency'])
                current_price_eur = self.api.convert_to_eur(price_data['price'], price_data['currency'])

                # Calculate dip from sale price
                dip_percent = ((current_price_eur - sale_price_eur) / sale_price_eur) * 100

                # Trigger if dip is between 10-15%
                if -15 <= dip_percent <= -10:
                    buy_opportunities.append({
                        'action': 'BUY',
                        'asset': asset,
                        'reason': f'Re-entry: {dip_percent:.2f}% from sale price',
                        'amount_eur': self.config['triggers']['buy_amount_eur'],
                        'price': price_data,
                        'remove_from_sold': True  # Flag to remove after buy
                    })
                    logger.info(f"Re-entry trigger: {asset} at {dip_percent:.2f}% from sale price")

        return buy_opportunities

    def can_afford_buy(self, amount_eur):
        """Check if we have sufficient budget for a buy"""
        fee = amount_eur * self.config['fees']['taker_fee_rate']
        total_cost = amount_eur + fee
        new_balance = self.current_eur_balance - total_cost

        return new_balance >= self.config['minimum_balance_eur']

    def execute_trade(self, action, asset, amount, price_data, is_full_exit=True):
        """Execute a trade (or simulate in dry-run mode)"""
        currency = price_data['currency']
        price = price_data['price']
        value = amount * price
        
        # Convert to EUR using centralized function
        value_eur = self.api.convert_to_eur(value, currency)
        
        # Calculate fees
        fee = value_eur * self.config['fees']['taker_fee_rate']
        
        if action == 'SELL':
            net_proceeds = value_eur - fee
            
            # Calculate P&L if we have position tracking
            profit_loss = 0
            if asset in self.config['position_tracking']:
                pos = self.config['position_tracking'][asset]
                
                # Calculate cost basis using centralized conversion
                cost_basis = amount * self.api.convert_to_eur(pos['entry_price'], pos['entry_currency'])
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
                        # Record sold position for re-entry tracking
                        self.record_sold_position(asset, price_data, amount)
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
                # Round amount to match product precision requirements (round DOWN for SELL)
                rounded_amount = self.api.round_to_precision(amount, product_id, "SELL")
                min_size = self.api.get_min_order_size(product_id)
                
                # Check if rounded amount meets minimum order size
                if min_size > 0 and rounded_amount < min_size:
                    print(f"  ⚠️  Position too small to sell: {rounded_amount:.8f} {asset} (min: {min_size})")
                    logger.warning(f"Skipping SELL order for {asset}: rounded amount {rounded_amount:.8f} is below minimum size {min_size} for {product_id}")
                    # Mark position with a flag to avoid logging repeatedly
                    if asset in self.config['position_tracking']:
                        pos = self.config['position_tracking'][asset]
                        if not pos.get('too_small_to_sell'):
                            pos['too_small_to_sell'] = True
                            self.save_config()
                    return
                
                logger.info(f"Placing SELL order: {rounded_amount:.8f} {asset} on {product_id} (original: {amount:.8f})")
                result = self.api.place_order(product_id, "SELL", rounded_amount, 'base_size')
                if result and result.get('success', False):
                    print(f"  ✅ SELL order placed: {result}")
                    logger.info(f"SELL order success: {result}")
                    self.current_eur_balance += net_proceeds

                    # Update position tracking
                    if asset in self.config['position_tracking']:
                        if is_full_exit:
                            # Record sold position for re-entry tracking
                            self.record_sold_position(asset, price_data, rounded_amount)
                            del self.config['position_tracking'][asset]
                        else:
                            pos = self.config['position_tracking'][asset]
                            pos['total_sold'] = pos.get('total_sold', 0.0) + rounded_amount
                        self.save_config()
                else:
                    error_msg = result.get('error_response', {}).get('message', 'Unknown error') if result else 'No response'
                    print(f"  ❌ SELL order failed: {error_msg}")
                    logger.error(f"SELL order failed for {asset}: {error_msg}")
        
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
                # Round quote amount to 2 decimals for fiat currencies
                rounded_value = round(value_eur, 2)
                logger.info(f"Placing BUY order: €{rounded_value:.2f} worth of {asset} on {product_id}")
                result = self.api.place_order(product_id, "BUY", rounded_value, 'quote_size')
                if result and result.get('success', False):
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
                    error_msg = result.get('error_response', {}).get('message', 'Unknown error') if result else 'No response'
                    print(f"  ❌ BUY order failed: {error_msg}")
                    logger.error(f"BUY order failed for {asset}: {error_msg}")
    
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

        # Track price history for buy assets (BTC, ETH)
        for asset in self.config['triggers'].get('buy_assets', []):
            price_data = self.get_price(asset)
            if price_data:
                self.track_price_history(asset, price_data)

        # Check each holding for triggers
        for asset, amount in holdings.items():
            print(f"\n  {asset}: {amount:.8f}")
            
            # Skip if position is flagged as too small to sell
            if asset in self.config.get('position_tracking', {}):
                if self.config['position_tracking'][asset].get('too_small_to_sell'):
                    print(f"    ⚠️  Position too small to sell (flagged)")
                    continue
            
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

        # Check for buy opportunities
        buy_triggers = self.check_buy_triggers()
        if buy_triggers:
            print(f"\n🎯 Found {len(buy_triggers)} buy opportunity/opportunities")
            for trigger in buy_triggers:
                if self.can_afford_buy(trigger['amount_eur']):
                    print(f"  {trigger['reason']}")
                    # Calculate amount in base currency
                    amount_base = trigger['amount_eur'] / trigger['price']['price']
                    self.execute_trade('BUY', trigger['asset'], amount_base, trigger['price'])

                    # Remove from sold positions if this was a re-entry
                    if trigger.get('remove_from_sold', False):
                        if 'sold_positions' in self.config and trigger['asset'] in self.config['sold_positions']:
                            del self.config['sold_positions'][trigger['asset']]
                            self.save_config()
                            logger.info(f"Removed {trigger['asset']} from sold positions after re-entry")
                else:
                    print(f"  ⚠️  Skipping {trigger['asset']}: Insufficient budget")
                    logger.warning(f"Insufficient budget for buy: {trigger['asset']}, need €{trigger['amount_eur']}")

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
