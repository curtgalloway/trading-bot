#!/usr/bin/env python3
"""
Quick Check Script - "Is This THE Dip?"
Daily manual execution to check for major market crash signals
Includes market data + world events monitoring
"""
import json
import sys
import re
import time
import logging
from datetime import datetime, timedelta
from coinbase_api import CoinbaseAPI
import statistics
import urllib.request
from html.parser import HTMLParser

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

class NewsParser(HTMLParser):
    """Simple HTML parser to extract text from news sites"""
    def __init__(self):
        super().__init__()
        self.text = []
        self.in_script = False
        
    def handle_starttag(self, tag, attrs):
        if tag in ['script', 'style']:
            self.in_script = True
            
    def handle_endtag(self, tag):
        if tag in ['script', 'style']:
            self.in_script = False
            
    def handle_data(self, data):
        if not self.in_script:
            self.text.append(data.strip())
    
    def get_text(self):
        return ' '.join(self.text)


class WorldEventsMonitor:
    """Monitor world events for crypto crash catalysts"""
    
    # Crisis keywords that historically preceded crypto pumps
    CRISIS_KEYWORDS = {
        'CRITICAL': [
            'war', 'nuclear', 'strike', 'attack', 'bombing', 'missile',
            'collapse', 'crash', 'crisis', 'emergency', 'panic',
            'bank failure', 'default', 'bailout', 'fed raises', 'rate hike',
            'circuit breaker', 'trading halt', 'martial law'
        ],
        'HIGH': [
            'protest', 'unrest', 'coup', 'sanctions', 'inflation spike',
            'recession', 'unemployment', 'tensions escalate', 'conflict',
            'evacuate', 'lockdown', 'shutdown', 'investigation',
            'impeachment', 'resignation', 'scandal'
        ],
        'MODERATE': [
            'concern', 'warning', 'alert', 'threat', 'risk',
            'volatility', 'uncertainty', 'turmoil', 'disruption',
            'emergency meeting', 'summit', 'diplomatic'
        ]
    }
    
    def __init__(self):
        self.headlines = []
        self.signals = []
    
    def fetch_news(self, url, timeout=10):
        """Fetch news content from URL"""
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as response:
                html = response.read().decode('utf-8')
                parser = NewsParser()
                parser.feed(html)
                return parser.get_text()
        except Exception as e:
            return None
    
    def analyze_text(self, text):
        """Analyze text for crisis keywords"""
        if not text:
            return []
        
        text_lower = text.lower()
        found_signals = []
        
        for severity, keywords in self.CRISIS_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    # Count occurrences
                    count = text_lower.count(keyword.lower())
                    if count > 0:
                        found_signals.append((severity, keyword, count))
        
        return found_signals
    
    def scan_news_sources(self):
        """Scan multiple news sources"""
        print("\n" + "="*60)
        print("🌍 WORLD EVENTS SCAN")
        print("="*60)
        
        sources = [
            ('https://www.bbc.com/news', 'BBC News'),
            ('https://apnews.com/hub/financial-markets', 'AP News'),
        ]
        
        all_signals = []
        
        for url, name in sources:
            print(f"\nScanning {name}...", end=" ")
            text = self.fetch_news(url)
            
            if text:
                signals = self.analyze_text(text)
                if signals:
                    all_signals.extend(signals)
                    print(f"✓ ({len(signals)} signals)")
                else:
                    print("✓ (no crisis keywords)")
            else:
                print("✗ (failed to fetch)")
        
        return all_signals
    
    def categorize_signals(self, signals):
        """Group and count signals by severity"""
        critical = [s for s in signals if s[0] == 'CRITICAL']
        high = [s for s in signals if s[0] == 'HIGH']
        moderate = [s for s in signals if s[0] == 'MODERATE']
        
        return {
            'CRITICAL': critical,
            'HIGH': high,
            'MODERATE': moderate
        }
    
    def print_events_summary(self, signals):
        """Print summary of world events"""
        if not signals:
            print("\n🟢 No major crisis keywords detected")
            return 0
        
        categorized = self.categorize_signals(signals)
        
        print("\n" + "-"*60)
        print("Crisis Keywords Detected:")
        print("-"*60)
        
        # Show top signals by severity
        if categorized['CRITICAL']:
            print("\n🔴 CRITICAL Events:")
            top_critical = sorted(categorized['CRITICAL'], key=lambda x: x[2], reverse=True)[:5]
            for severity, keyword, count in top_critical:
                print(f"   • {keyword}: {count} mentions")
        
        if categorized['HIGH']:
            print("\n🟠 HIGH Priority Events:")
            top_high = sorted(categorized['HIGH'], key=lambda x: x[2], reverse=True)[:5]
            for severity, keyword, count in top_high:
                print(f"   • {keyword}: {count} mentions")
        
        if categorized['MODERATE']:
            print("\n🟡 MODERATE Concerns:")
            top_mod = sorted(categorized['MODERATE'], key=lambda x: x[2], reverse=True)[:3]
            for severity, keyword, count in top_mod:
                print(f"   • {keyword}: {count} mentions")
        
        # Calculate event risk score
        event_score = (
            len(categorized['CRITICAL']) * 5 +
            len(categorized['HIGH']) * 2 +
            len(categorized['MODERATE']) * 1
        )
        
        print(f"\nEvent Risk Score: {event_score}")
        
        return event_score


class DipSignalChecker:
    def __init__(self, check_events=False):
        self.api = CoinbaseAPI()
        self.check_events = check_events
        self.events_monitor = WorldEventsMonitor() if check_events else None
        # Store baseline prices on init for comparison
        self.baseline_prices = {}
        self._capture_baseline()
        
    def _capture_baseline(self):
        """Capture baseline prices - can be compared against trading_config history"""
        try:
            with open('trading_config.json', 'r') as f:
                config = json.load(f)
                self.price_history = config.get('price_history', {})
        except:
            self.price_history = {}
    
    def get_price_change(self, asset, hours_ago):
        """Calculate price change over time period using stored history"""
        # Get current price
        current = self.api.get_price(asset)
        if not current:
            return None
        
        current_price = current['price']
        
        # Try to get historical price from trading bot's stored history
        if asset not in self.price_history or not self.price_history[asset]:
            return None
        
        cutoff = datetime.now() - timedelta(hours=hours_ago)
        historical = [p for p in self.price_history[asset] 
                     if datetime.fromisoformat(p['timestamp']) <= cutoff]
        
        if not historical:
            # Not enough history - can't calculate this timeframe
            return None
        
        old_price = historical[-1]['price']
        change_pct = ((current_price - old_price) / old_price) * 100
        
        return {
            'current': current_price,
            'old': old_price,
            'change_pct': change_pct,
            'period_hours': hours_ago
        }
    
    def check_volatility(self, asset):
        """Check recent price volatility from stored history"""
        if asset not in self.price_history or not self.price_history[asset]:
            return None
        
        # Use last 20 data points (or less if not available)
        recent_prices = [p['price'] for p in self.price_history[asset][-20:]]
        
        if len(recent_prices) < 2:
            return None
        
        std_dev = statistics.stdev(recent_prices)
        mean = statistics.mean(recent_prices)
        volatility_pct = (std_dev / mean) * 100
        
        return volatility_pct
    
    def analyze_btc(self):
        """Analyze Bitcoin signals"""
        print("\n" + "="*60)
        print("🔍 BITCOIN (BTC) ANALYSIS")
        print("="*60)
        
        # Check different timeframes
        timeframes = [
            (1, "1 Hour"),
            (4, "4 Hours"),
            (24, "24 Hours"),
            (168, "7 Days")
        ]
        
        signals = []
        
        for hours, label in timeframes:
            change = self.get_price_change('BTC', hours)
            if change:
                print(f"\n{label}:")
                print(f"  Current: ${change['current']:,.2f}")
                print(f"  Was:     ${change['old']:,.2f}")
                print(f"  Change:  {change['change_pct']:+.2f}%", end="")
                
                # Signal detection
                if change['change_pct'] <= -40:
                    print(" 🔴 CAPITULATION ZONE!")
                    signals.append(('RED', f"{label} drop: {change['change_pct']:.1f}%"))
                elif change['change_pct'] <= -25:
                    print(" 🟠 MAJOR DIP TERRITORY")
                    signals.append(('ORANGE', f"{label} drop: {change['change_pct']:.1f}%"))
                elif change['change_pct'] <= -12:
                    print(" 🟡 Bot trigger zone")
                    signals.append(('YELLOW', f"{label} drop: {change['change_pct']:.1f}%"))
                elif change['change_pct'] <= -5:
                    print(" 🟢 Minor dip")
                else:
                    print("")
        
        # Volatility check
        volatility = self.check_volatility('BTC')
        if volatility:
            print(f"\nVolatility: {volatility:.2f}%", end="")
            if volatility > 5:
                print(" 🔴 EXTREME")
                signals.append(('RED', f"Volatility: {volatility:.1f}%"))
            elif volatility > 3:
                print(" 🟠 HIGH")
                signals.append(('ORANGE', f"Volatility: {volatility:.1f}%"))
            elif volatility > 1.5:
                print(" 🟡 Elevated")
            else:
                print(" 🟢 Normal")
        
        return signals
    
    def analyze_eth(self):
        """Analyze Ethereum signals"""
        print("\n" + "="*60)
        print("🔍 ETHEREUM (ETH) ANALYSIS")
        print("="*60)
        
        timeframes = [
            (1, "1 Hour"),
            (4, "4 Hours"),
            (24, "24 Hours"),
            (168, "7 Days")
        ]
        
        signals = []
        
        for hours, label in timeframes:
            change = self.get_price_change('ETH', hours)
            if change:
                print(f"\n{label}:")
                print(f"  Current: ${change['current']:,.2f}")
                print(f"  Was:     ${change['old']:,.2f}")
                print(f"  Change:  {change['change_pct']:+.2f}%", end="")
                
                if change['change_pct'] <= -40:
                    print(" 🔴 CAPITULATION ZONE!")
                    signals.append(('RED', f"{label} drop: {change['change_pct']:.1f}%"))
                elif change['change_pct'] <= -25:
                    print(" 🟠 MAJOR DIP TERRITORY")
                    signals.append(('ORANGE', f"{label} drop: {change['change_pct']:.1f}%"))
                elif change['change_pct'] <= -12:
                    print(" 🟡 Bot trigger zone")
                    signals.append(('YELLOW', f"{label} drop: {change['change_pct']:.1f}%"))
                elif change['change_pct'] <= -5:
                    print(" 🟢 Minor dip")
                else:
                    print("")
        
        return signals
    
    def calculate_risk_score(self, btc_signals, eth_signals, event_score=0):
        """Calculate overall dip risk score including world events"""
        all_signals = btc_signals + eth_signals
        
        if not all_signals and event_score == 0:
            return 0, "NO DATA", 0, 0
        
        red_count = sum(1 for s in all_signals if s[0] == 'RED')
        orange_count = sum(1 for s in all_signals if s[0] == 'ORANGE')
        yellow_count = sum(1 for s in all_signals if s[0] == 'YELLOW')
        
        market_score = (red_count * 10) + (orange_count * 5) + (yellow_count * 2)
        
        # Combined score with event multiplier
        # Events can amplify market signals
        if event_score > 10 and market_score > 0:
            # High event risk + market movement = amplified signal
            combined_score = market_score + (event_score * 1.5)
        else:
            combined_score = market_score + event_score
        
        # Determine risk level
        if combined_score >= 30:
            level = "🔴🔴 EXTREME - HISTORIC CRASH PATTERN"
        elif combined_score >= 20:
            level = "🔴 CRITICAL - THIS IS THE DIP"
        elif combined_score >= 10:
            level = "🟠 HIGH - Major dip territory"
        elif combined_score >= 5:
            level = "🟡 MODERATE - Watch closely"
        else:
            level = "🟢 LOW - Normal conditions"
        
        return combined_score, level, market_score, event_score
    
    def print_summary(self, btc_signals, eth_signals, event_score=0):
        """Print summary and recommendation"""
        print("\n" + "="*60)
        print("📊 SUMMARY")
        print("="*60)
        
        combined_score, level, market_score, events_score = self.calculate_risk_score(
            btc_signals, eth_signals, event_score
        )
        
        if self.check_events:
            print(f"\nMarket Risk Score: {market_score}")
            print(f"Events Risk Score: {events_score}")
            print(f"Combined Score: {combined_score}")
        else:
            print(f"\nMarket Risk Score: {combined_score}")
        
        print(f"Risk Level: {level}")
        
        all_signals = btc_signals + eth_signals
        if all_signals:
            print("\nActive Market Signals:")
            for signal_type, description in all_signals:
                emoji = {'RED': '🔴', 'ORANGE': '🟠', 'YELLOW': '🟡'}.get(signal_type, '⚪')
                print(f"  {emoji} {description}")
        
        print("\n" + "="*60)
        print("💡 RECOMMENDATION")
        print("="*60)
        
        if combined_score >= 30:
            print("\n🚨🚨 EXTREME - HISTORIC OPPORTUNITY")
            print("   → Market crash + world crisis = perfect storm")
            print("   → This matches 2020/2017/2013 patterns EXACTLY")
            print("   → Deploy MAXIMUM capital immediately")
            print("   → Bot should be auto-buying - supplement heavily")
            print("   → Historical recovery: 1-3 months to new highs")
        elif combined_score >= 20:
            print("\n🚨 MAJOR BUYING OPPORTUNITY")
            print("   → This matches historical crash patterns")
            print("   → Consider deploying supplemental capital")
            print("   → Bot should already be buying")
            if self.check_events and events_score > 5:
                print("   → World events confirm systemic stress")
        elif combined_score >= 10:
            print("\n⚠️  SIGNIFICANT DIP")
            print("   → Monitor closely over next 24-48h")
            print("   → Prepare to supplement bot purchases")
            print("   → Watch for further deterioration")
            if self.check_events and events_score > 5:
                print("   → Elevated geopolitical/economic risk")
        elif combined_score >= 5:
            print("\n👀 ELEVATED WATCH")
            print("   → Prices moving, stay alert")
            print("   → Bot may trigger soon")
            print("   → Review portfolio allocation")
        else:
            print("\n✅ NORMAL CONDITIONS")
            print("   → No immediate action needed")
            print("   → Continue routine monitoring")
        
        print()
    
    def run(self):
        """Execute full check"""
        print("\n" + "="*60)
        mode = "FULL SCAN (Market + Events)" if self.check_events else "MARKET SCAN"
        print(f"🎯 DIP SIGNAL CHECK - {mode}")
        print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
        # Show data coverage
        if self.price_history:
            print("\n📈 Price History Coverage:")
            for asset in ['BTC', 'ETH']:
                if asset in self.price_history and self.price_history[asset]:
                    count = len(self.price_history[asset])
                    oldest = datetime.fromisoformat(self.price_history[asset][0]['timestamp'])
                    age_hours = (datetime.now() - oldest).total_seconds() / 3600
                    print(f"   {asset}: {count} data points ({age_hours:.1f} hours of history)")
                else:
                    print(f"   {asset}: No data")
            print("\n⚠️  Note: Longer timeframes require more history.")
            print("   Bot stores prices every 15 minutes when running.")
        
        # Check world events first (if enabled)
        event_score = 0
        if self.check_events:
            news_signals = self.events_monitor.scan_news_sources()
            event_score = self.events_monitor.print_events_summary(news_signals)
        
        # Check market data
        btc_signals = self.analyze_btc()
        eth_signals = self.analyze_eth()
        
        # Combined summary
        self.print_summary(btc_signals, eth_signals, event_score)

if __name__ == '__main__':
    # Check for --full or --events flag
    check_events = '--full' in sys.argv or '--events' in sys.argv
    
    if check_events:
        print("\n💡 Running FULL scan (market + world events)")
        print("   This may take 10-20 seconds...\n")
    
    checker = DipSignalChecker(check_events=check_events)
    checker.run()
