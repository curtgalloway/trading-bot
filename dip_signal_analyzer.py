#!/usr/bin/env python3
"""
Dip Signal Analyzer — Market microstructure + macro overlay
for the crypto trading bot.

Replaces check_dip_signals.py with real signal data instead of
keyword-counting on news homepages.

Signal philosophy:
  - Funding rates tell you about positioning/crowdedness
  - Liquidation cascades signal capitulation (buy zone) or continued pressure
  - Price action + volatility tell you where we are
  - Macro events are context, not signals
  - Recommendations are always scaled, never "all-in"

Data sources (all free, no API keys needed):
  - Binance REST API (funding rates, open interest, liquidations)
  - CoinGecko (stablecoin supply)
  - Yahoo Finance (VIX) — optional, best-effort

Usage:
  python3 dip_signal_analyzer.py         # quick scan (~15s)
  python3 dip_signal_analyzer.py --full  # full report (~30s, includes macro)
  python3 dip_signal_analyzer.py --json  # machine-readable output
  python3 dip_signal_analyzer.py --history  # check against price history
"""

import json
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

from coinbase_api import CoinbaseAPI

# ─── Config ───────────────────────────────────────────────────────────────────

BINANCE_BASE = "https://fapi.binance.com"
YAHOO_FINANCE = "https://query1.finance.yahoo.com"
COINGECKO = "https://api.coingecko.com/api/v3"

# Weighting for the composite dip score (sum to 1.0)
SIGNAL_WEIGHTS = {
    "funding_rate":     0.25,  # positioning/crowdedness
    "liquidations":     0.10,  # capitulation detector (best-effort)
    "fear_and_greed":   0.15,  # sentiment indicator (works well)
    "price_action":     0.25,  # where are we relative to key levels?
    "volatility":       0.05,  # regime assessment
    "macro_overlay":    0.20,  # context, not driver
}

# Signal thresholds — these define what counts as "extreme"
# Funding: annualized, negative = shorts dominating = potential bounce
# Liquidations: total USD wiped in last 24h
PRICE_ZONES = {
    "capitulation": 0.25,   # 25%+ drop → extreme buy zone
    "major_dip":    0.15,   # 15-25% → buy opportunity
    "moderate_dip": 0.05,   # 5-15% → normal dip zone
}


# ─── Data Fetchers ───────────────────────────────────────────────────────────

def fetch_json(url: str, timeout: int = 10) -> Optional[Any]:
    """Fetch JSON with retry, return None on failure."""
    if HAS_REQUESTS:
        try:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    headers = {"User-Agent": "Mozilla/5.0 (trading-bot)"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def get_btc_eth_current():
    """Get current BTC/ETH prices from Coinbase."""
    api = CoinbaseAPI()
    result = {}
    for asset in ["BTC", "ETH"]:
        try:
            price_data = api.get_price(asset)
            if price_data:
                result[asset] = {
                    "price": price_data["price"],
                    "currency": price_data.get("currency", "USDC"),
                    "pair": price_data.get("pair", f"{asset}-USDC"),
                }
        except Exception:
            result[asset] = None
    return result


def get_binance_funding_rate(symbol: str = "BTCUSDT") -> Optional[Dict]:
    """
    Get current funding rate and open interest.
    Funding rate is per 8h, annualized = rate * 3 * 365 * 100
    Positive = longs pay shorts (bullish sentiment).
    Negative = shorts pay longs (bearish/capitulation sentiment).
    """
    url = f"{BINANCE_BASE}/fapi/v1/premiumIndex?symbol={symbol}"
    data = fetch_json(url)
    if not data:
        return None

    funding_rate = float(data.get("lastFundingRate", 0))
    mark_price = float(data.get("markPrice", 0))
    index_price = float(data.get("indexPrice", 0))

    # Annualized funding % (multiply: 3 times per day * 365 days)
    annualized = funding_rate * 3 * 365 * 100

    # Open interest
    oi_url = f"{BINANCE_BASE}/fapi/v1/openInterest?symbol={symbol}"
    oi_data = fetch_json(oi_url)
    open_interest = None
    if oi_data and "openInterest" in oi_data:
        open_interest = float(oi_data["openInterest"])

    return {
        "symbol": symbol,
        "funding_rate": funding_rate,
        "annualized_funding_pct": round(annualized, 3),
        "mark_price": mark_price,
        "index_price": index_price,
        "open_interest": open_interest,
        "timestamp": datetime.now().isoformat(),
    }


def get_binance_liquidations(symbol: str = "BTCUSDT", limit: int = 50) -> Optional[Dict]:
    """
    Get recent liquidations (force closures of leveraged positions).
    Large cascades near bottom → capitulation (buy signal).
    Large cascades on way down → continued pressure.
    """
    url = f"{BINANCE_BASE}/fapi/v1/liqOrders"
    params = urllib.parse.urlencode({
        "symbol": symbol,
        "limit": limit,
    })
    data = fetch_json(f"{url}?{params}")
    if not data:
        return None

    # data is a list of liquidation records
    longs = [e for e in data if e.get("side") == "BUY"]   # short liquidated
    shorts = [e for e in data if e.get("side") == "SELL"] # long liquidated

    total_long_liquidated_usd = sum(float(e.get("qty", 0)) * float(e.get("price", 0)) for e in longs)
    total_short_liquidated_usd = sum(float(e.get("qty", 0)) * float(e.get("price", 0)) for e in shorts)

    return {
        "symbol": symbol,
        "total_liq_usd": round(total_long_liquidated_usd + total_short_liquidated_usd, 2),
        "long_liq_usd": round(total_long_liquidated_usd, 2),
        "short_liq_usd": round(total_short_liquidated_usd, 2),
        "long_count": len(longs),
        "short_count": len(shorts),
        "recent_liqs": sorted(data, key=lambda x: x.get("time", 0), reverse=True)[:10],
        "timestamp": datetime.now().isoformat(),
    }


def get_stablecoin_supply() -> Optional[Dict]:
    """
    Track USDC and USDT supply changes.
    Net minting = new capital flowing in (bullish).
    Net burning = capital leaving (bearish).
    """
    # CoinGecko free endpoint for USDC and USDT
    ids = "usd-coin,tether"
    url = f"{COINGECKO}/simple/price?ids={ids}&vs_currencies=market_cap"
    data = fetch_json(url)
    if not data:
        return None

    return {
        "usdc_market_cap": data.get("usd-coin", {}).get("usd"),
        "usdt_market_cap": data.get("tether", {}).get("usd"),
        "total_stablecap": (
            data.get("usd-coin", {}).get("usd", 0) +
            data.get("tether", {}).get("usd", 0)
        ),
    }


def get_vix() -> Optional[float]:
    """
    Get VIX (CBOE Volatility Index) from Yahoo Finance.
    VIX > 30 = fear territory. VIX < 15 = complacency.
    High VIX during crypto dip = capitulation (good buy zone).
    High VIX not during dip = general fear (caution).
    """
    # Use the VIX ticker data
    try:
        if HAS_REQUESTS:
            resp = requests.get(
                f"{YAHOO_FINANCE}/v8/finance/chart/%5EVIX",
                params={"interval": "1d", "range": "5d"},
                timeout=10,
            )
            data = resp.json().get("chart", {}).get("result", [{}])[0]
            closes = data.get("indicators", {}).get("quote", [{}])[0].get("close")
            closes = [c for c in closes if c is not None]
            return round(closes[-1], 2) if closes else None
    except Exception:
        pass

    return None


def get_dxy() -> Optional[float]:
    """
    Get US Dollar Index (DXY).
    Strong dollar → crypto pressure. Weak dollar → tailwind.
    """
    try:
        if HAS_REQUESTS:
            resp = requests.get(
                f"{YAHOO_FINANCE}/v8/finance/chart/%5EDXY",
                params={"interval": "1d", "range": "5d"},
                timeout=10,
            )
            data = resp.json().get("chart", {}).get("result", [{}])[0]
            closes = data.get("indicators", {}).get("quote", [{}])[0].get("close")
            closes = [c for c in closes if c is not None]
            return round(closes[-1], 2) if closes else None
    except Exception:
        pass

    return None


# ─── Signal Analysis ─────────────────────────────────────────────────────────

def analyze_funding_rate(funding: Dict) -> Dict:
    """
    Analyze funding rate signal.
    Negative annualized = shorts dominating → potential bounce (buy signal).
    High positive (>200%/yr) = longs crowded → potential flush (caution).
    Near zero = neutral/balanced market.
    """
    ann = funding.get("annualized_funding_pct", 0)
    score = 0  # -100 (bearish) to +100 (bullish/capitulation)

    if ann < -10:
        score = 80   # massive capitulation
        signal = "EXTREME capitulation — shorts paying heavily"
        emoji = "🟢"
    elif ann < -5:
        score = 50   # significant bearish pressure
        signal = "Bearish pressure building"
        emoji = "🟡"
    elif ann < 0:
        score = 20
        signal = "Slightly bearish"
        emoji = "⚪"
    elif ann < 10:
        score = -20
        signal = "Neutral/balanced"
        emoji = "⚪"
    elif ann < 50:
        score = -50
        signal = "Crowded longs"
        emoji = "🟡"
    else:
        score = -80
        signal = "Extremely crowded longs — flush risk"
        emoji = "🔴"

    return {
        "signal": signal,
        "emoji": emoji,
        "score": score,
        "annualized_pct": ann,
        "current_rate": funding.get("funding_rate", 0),
        "open_interest": funding.get("open_interest"),
    }



def get_fear_and_greed() -> Optional[Dict]:
    """
    Crypto Fear & Greed Index (alternative.me).
    Free, reliable, crypto-specific sentiment indicator.
    Returns None on failure (best-effort).
    """
    url = "https://api.alternative.me/fng/"
    data = fetch_json(url)
    if not data or "data" not in data:
        return None

    entry = data["data"][0]
    value = int(entry["value"])
    classification = entry["value_classification"]

    # Score: negative greed = good for buys (fear = capitulation)
    if value < 15:
        score = 90
        signal = "Extreme fear — capitulation zone"
        emoji = "🟢"
    elif value < 25:
        score = 60
        signal = "Fear — buying opportunity"
        emoji = "🟢"
    elif value < 40:
        score = 30
        signal = "Fear — watch for deeper dip"
        emoji = "🟡"
    elif value < 60:
        score = 0
        signal = "Neutral"
        emoji = "⚪"
    elif value < 75:
        score = -30
        signal = "Greed — market bullish"
        emoji = "⚪"
    else:
        score = -60
        signal = "Extreme greed — overextended"
        emoji = "🔴"

    return {
        "score": score,
        "signal": signal,
        "emoji": emoji,
        "value": value,
        "classification": classification,
    }


def analyze_fear_and_greed(fg: Optional[Dict]) -> Dict:
    """Analyze Fear & Greed Index as a standalone signal."""
    if not fg:
        return {"signal": "Unavailable", "emoji": "⚠️", "score": 0}

    return {
        "signal": fg["signal"],
        "emoji": fg["emoji"],
        "score": fg["score"],
        "value": fg["value"],
        "classification": fg["classification"],
    }



def analyze_liquidations(liq: Dict) -> Dict:
    """
    Analyze liquidation data.
    Big liquidation cascades = potential capitulation (buy zone).
    But context matters: are we falling or stabilizing?
    """
    total = liq.get("total_liq_usd", 0)
    long_liq = liq.get("long_liq_usd", 0)  # shorts getting liquidated
    short_liq = liq.get("short_liq_usd", 0)  # longs getting liquidated

    score = 0  # -100 to +100
    direction = "neutral"

    if total < 500_000:
        signal = "No significant liquidations"
        emoji = "⚪"
    elif total < 5_000_000:
        score = -10
        signal = "Minor liquidation activity"
        emoji = "⚪"
    elif total < 20_000_000:
        score = 30
        direction = "capitulation"
        signal = "Moderate liquidation cascade"
        emoji = "🟡"
    else:
        score = 70
        direction = "capitulation"
        signal = "Major liquidation cascade — capitulation signal"
        emoji = "🟢"

    # Detail: are shorts or longs getting wrecked?
    short_wreckage = short_liq > total * 0.6
    long_wreckage = long_liq > total * 0.6

    return {
        "signal": signal,
        "emoji": emoji,
        "score": score,
        "direction": direction,
        "total_usd": total,
        "longs_liquidated_usd": short_liq,  # shorts liquidated = longs won
        "shorts_liquidated_usd": long_liq,   # longs liquidated = shorts won
        "short_wreckage": short_wreckage,
        "long_wreckage": long_wreckage,
    }


def analyze_price_action(current: Dict, history: Dict) -> Dict:
    """
    Where is price relative to recent ranges and key levels?
    """
    results = {}

    for asset in ["BTC", "ETH"]:
        price_info = current.get(asset)
        if not price_info:
            results[asset] = None
            continue

        price = price_info["price"]
        hist = history.get(asset, [])

        analysis = {
            "current_price": price,
            "change_24h": None,
            "change_7d": None,
            "zone": "normal",
            "score": 0,
            "signal": "Price stable",
            "emoji": "⚪",
        }

        if hist:
            # Find oldest entry
            oldest_ts = min(p["timestamp"] for p in hist)
            oldest = min(hist, key=lambda p: p["timestamp"])
            seven_days_ago = datetime.now() - timedelta(days=7)

            # 24h change (rough: use recent entries)
            recent_24h = [p for p in hist if datetime.fromisoformat(p["timestamp"]) > datetime.now() - timedelta(hours=24)]
            if recent_24h:
                price_24h = recent_24h[0]["price"]
                change_24h = ((price - price_24h) / price_24h) * 100
                analysis["change_24h"] = round(change_24h, 2)

            # 7d change
            old_entry = min(hist, key=lambda p: datetime.fromisoformat(p["timestamp"]))
            change_7d = ((price - old_entry["price"]) / old_entry["price"]) * 100
            analysis["change_7d"] = round(change_7d, 2)

            # Determine zone
            if change_24h and change_24h <= -PRICE_ZONES["capitulation"]:
                analysis["zone"] = "capitulation"
                analysis["score"] = 80
                analysis["signal"] = "Capitulation zone"
                analysis["emoji"] = "🟢"
            elif change_24h and change_24h <= -PRICE_ZONES["major_dip"]:
                analysis["zone"] = "major_dip"
                analysis["score"] = 50
                analysis["signal"] = "Major dip territory"
                analysis["emoji"] = "🟡"
            elif change_24h and change_24h <= -PRICE_ZONES["moderate_dip"]:
                analysis["zone"] = "moderate_dip"
                analysis["score"] = 20
                analysis["signal"] = "Moderate dip"
                analysis["emoji"] = "⚪"

        results[asset] = analysis

    return results


def analyze_volatility(price_history: Dict) -> Dict:
    """
    Calculate 24h and 7d volatility from price history.
    High volatility during a dip = fear/selling.
    Low volatility during a dip = orderly correction.
    """
    import statistics

    results = {}
    for asset in ["BTC", "ETH"]:
        hist = price_history.get(asset, [])
        if len(hist) < 3:
            results[asset] = {"24h_vol": None, "7d_vol": None, "interpretation": "insufficient data"}
            continue

        # Group by time bucket
        now = datetime.now()
        prices_24h = []
        prices_7d = []

        for p in hist:
            ts = datetime.fromisoformat(p["timestamp"])
            prices_24h.append(p["price"])
            if ts > now - timedelta(days=7):
                prices_7d.append(p["price"])

        vol_24h = (statistics.stdev(prices_24h) / statistics.mean(prices_24h) * 100) if len(prices_24h) > 2 else 0
        vol_7d = (statistics.stdev(prices_7d) / statistics.mean(prices_7d) * 100) if len(prices_7d) > 2 else 0

        results[asset] = {
            "24h_vol_pct": round(vol_24h, 3),
            "7d_vol_pct": round(vol_7d, 3),
        }

    return results


def analyze_macro(vix: Optional[float], dxy: Optional[float], fg_index: Optional[Dict]) -> Dict:
    """
    Macro overlay: VIX, DXY, and Fear & Greed context.
    Fear & Greed is the star — free, reliable, crypto-specific.
    VIX/DXY are traditional market context (best-effort).
    """
    result = {"vix": vix, "dxy": dxy, "fear_and_greed": fg_index, "interpretations": []}

    if fg_index is not None:
        result["interpretations"].append(f"F&G Index: {fg_index['value']}/100 ({fg_index['classification']})")
        if fg_index["value"] < 20:
            result["fg_signal"] = "capitulation"
            result["interpretations"].append("  → Extreme fear in crypto — historically strong buy zone")
        elif fg_index["value"] < 35:
            result["fg_signal"] = "fear"
            result["interpretations"].append("  → Fear in crypto — buying opportunity forming")
        elif fg_index["value"] < 60:
            result["fg_signal"] = "neutral"
            result["interpretations"].append("  → Neutral sentiment")
        elif fg_index["value"] < 75:
            result["fg_signal"] = "greed"
            result["interpretations"].append("  → Greed in crypto — watch for overheating")
        else:
            result["fg_signal"] = "extreme_greed"
            result["interpretations"].append("  → Extreme greed — overextended, pullback risk")

    if vix is not None:
        if vix > 35:
            result["interpretations"].append(f"VIX: {vix:.1f} (extreme — panic in equities)")
        elif vix > 25:
            result["interpretations"].append(f"VIX: {vix:.1f} (elevated — fear in equities)")
        else:
            result["interpretations"].append(f"VIX: {vix:.1f} (calm)")

    if dxy is not None:
        if dxy > 108:
            result["interpretations"].append(f"DXY: {dxy:.1f} (strong dollar — headwind)")
        elif dxy < 102:
            result["interpretations"].append(f"DXY: {dxy:.1f} (weak dollar — tailwind)")
        else:
            result["interpretations"].append(f"DXY: {dxy:.1f} (neutral)")

    if not result["interpretations"]:
        result["interpretations"].append("Macro data unavailable")

    return result


# ─── Score Aggregation ────────────────────────────────────────────────────────

def aggregate_score(
    funding: Optional[Dict],
    liquidations: Optional[Dict],
    price_action: Dict,
    volatility: Dict,
    macro: Dict,
    fg: Optional[Dict] = None,
) -> Dict:
    """
    Aggregate all signals into a single dip opportunity score.
    Score: 0-100, where 100 = extreme buy opportunity (capitulation + crowded shorts).
    """
    scores = {"funding_rate": 0, "liquidations": 0, "fear_and_greed": 0, "price_action": 0, "volatility": 0, "macro_overlay": 0}
    details = {}

    # Funding rate signal
    if funding:
        s = analyze_funding_rate(funding)
        scores["funding_rate"] = s["score"]
        details["funding"] = s
    else:
        details["funding"] = {"signal": "Unavailable", "emoji": "⚠️"}

    # Fear & Greed signal
    if fg:
        s = analyze_fear_and_greed(fg)
        scores["fear_and_greed"] = s["score"]
        details["fear_and_greed"] = s
    else:
        details["fear_and_greed"] = {"signal": "Unavailable", "emoji": "⚠️"}

    # Liquidation signal
    if liquidations:
        s = analyze_liquidations(liquidations)
        scores["liquidations"] = s["score"]
        details["liquidations"] = s
    else:
        details["liquidations"] = {"signal": "Unavailable", "emoji": "⚠️"}

    # Price action
    btc_pa = price_action.get("BTC")
    eth_pa = price_action.get("ETH")
    if btc_pa and btc_pa["change_24h"] is not None:
        scores["price_action"] = btc_pa["score"]
        details["price_action"] = {
            "btc": btc_pa,
            "eth": eth_pa,
        }
    else:
        details["price_action"] = {"signal": "Insufficient history", "emoji": "⚠️"}

    # Volatility
    if volatility:
        btc_vol = volatility.get("BTC", {}).get("24h_vol")
        if btc_vol and btc_vol > 5:
            scores["volatility"] = 30  # high vol during dip = fear/capitulation
        elif btc_vol and btc_vol > 2:
            scores["volatility"] = 10
        else:
            scores["volatility"] = 0
        details["volatility"] = volatility
    else:
        details["volatility"] = {"interpretation": "Unavailable", "emoji": "⚠️"}

    # Macro (context only, moderate weight)
    if macro:
        vix = macro.get("vix")
        if vix and vix > 30:
            scores["macro_overlay"] = 20  # equities in panic = crypto may follow
        elif vix and vix > 20:
            scores["macro_overlay"] = 10
        else:
            scores["macro_overlay"] = 0
        details["macro"] = macro
    else:
        details["macro"] = {"interpretations": ["Macro data unavailable"], "emoji": "⚠️"}

    # Weighted composite
    composite = sum(scores[k] * SIGNAL_WEIGHTS[k] for k in scores)
    composite = round(min(100, max(0, composite)), 1)

    # Determine recommendation
    if composite >= 65:
        recommendation = {
            "action": "STRONG BUY OPPORTUNITY",
            "confidence": "high",
            "guide": (
                "Multiple signals align: capitulation detected. "
                "This is a zone where you'd want to deploy supplemental capital. "
                "Scale in: 25% now, 25% on further dip, 50% as stabilization confirms. "
                "Do NOT deploy 100% — the bottom may be deeper."
            ),
        }
    elif composite >= 45:
        recommendation = {
            "action": "BUYING OPPORTUNITY",
            "confidence": "moderate",
            "guide": (
                "Dip detected with supporting signals. "
                "Bot should be triggering its buy-the-dip soon. "
                "Consider adding supplemental capital if balance allows: "
                "deploy 30% now, keep 70% in reserve for further moves."
            ),
        }
    elif composite >= 25:
        recommendation = {
            "action": "MODERATE DIP — WATCH",
            "confidence": "low-moderate",
            "guide": (
                "Some dip detected but signals are mixed. "
                "Let the bot trigger naturally. "
                "No need to supplement unless it drops further."
            ),
        }
    elif composite >= 10:
        recommendation = {
            "action": "NORMAL CONDITIONS",
            "confidence": "low",
            "guide": (
                "No significant dip signals. "
                "Continue routine monitoring. "
                "Bot's buy-dip trigger should wait for 5%+ drop."
            ),
        }
    else:
        recommendation = {
            "action": "POSITIVE / NO DIP",
            "confidence": "low",
            "guide": (
                "No dip conditions. Prices stable or rising. "
                "No need to supplement the bot."
            ),
        }

    return {
        "composite_score": composite,
        "scores": scores,
        "details": details,
        "recommendation": recommendation,
        "timestamp": datetime.now().isoformat(),
    }


# ─── Output Formatting ───────────────────────────────────────────────────────

def print_banner(title: str, subtitle: str = ""):
    print(f"\n{'='*70}")
    print(f"{'='*70}")


def format_scan(aggregate: Dict, current_prices: Dict, mode: str = "text") -> str:
    """Format the full scan results."""
    lines = []

    lines.append("")
    lines.append("=" * 70)
    lines.append(f"  🎯 DIP SIGNAL ANALYZER")
    lines.append(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 70)

    # Current prices
    lines.append("\n💰 Current Prices:")
    for asset in ["BTC", "ETH"]:
        p = current_prices.get(asset)
        if p:
            lines.append(f"  {asset}: ${p['price']:,.2f} ({p.get('currency', 'USDC')})")

    # Composite score
    score = aggregate["composite_score"]
    score_color = "🟢" if score >= 65 else "🟡" if score >= 35 else "⚪"
    lines.append(f"\n📊 Composite Dip Score: {score_color} {score:.0f}/100")
    lines.append(f"   0 = no opportunity  |  35 = moderate  |  65+ = strong buy zone")

    # Signal breakdown
    lines.append("\n📡 Signal Breakdown:")
    details = aggregate["details"]

    # Fear & Greed
    fg = details.get("fear_and_greed", {})
    lines.append(f"\n  {'='*50}")
    lines.append(f"  Fear & Greed Index  {fg.get('emoji', '⚠️')}")
    lines.append(f"  {'='*50}")
    lines.append(f"  {fg.get('signal', 'Unavailable')}")
    fg_val = fg.get('value', None)
    if fg_val is not None:
        lines.append(f"  Score: {fg_val}/100 ({fg.get('classification', '')})")

    # Funding Rate
    f = details.get("funding", {})
    lines.append(f"\n  {'='*50}")
    lines.append(f"  Funding Rate (Longs vs Shorts)  {f.get('emoji', '⚠️')}")
    lines.append(f"  {'='*50}")
    lines.append(f"  {f.get('signal', 'Unavailable')}")
    ann = f.get('annualized_pct', None)
    if ann is not None:
        direction = "positive (longs paying)" if ann > 0 else "negative (shorts paying)"
        lines.append(f"  Annualized: {ann:+.2f}% ({direction})")
    oi = f.get('open_interest')
    if oi is not None:
        lines.append(f"  Open Interest: {oi}")

    # Liquidations
    l = details.get("liquidations", {})
    lines.append(f"\n  {'='*50}")
    lines.append(f"  Liquidation Activity  {l.get('emoji', '⚠️')}")
    lines.append(f"  {'='*50}")
    lines.append(f"  {l.get('signal', 'Unavailable')}")
    total = l.get('total_usd', 0)
    if total > 0:
        lines.append(f"  Total liquidated (24h): ${total:,.0f}")
        lines.append(f"  Shorts liquidated: ${l.get('shorts_liquidated_usd', 0):,.0f} (price drop)")
        lines.append(f"  Longs liquidated:  ${l.get('longs_liquidated_usd', 0):,.0f} (price rise)")
    if l.get('short_wreckage'):
        lines.append(f"  ⚡ Shorts getting liquidated → bullish pressure relief")
    if l.get('long_wreckage'):
        lines.append(f"  ⚡ Longs getting liquidated → continued selling pressure")

    # Price action
    pa = details.get("price_action", {})
    if isinstance(pa, dict) and "btc" in pa:
        lines.append(f"\n  {'='*50}")
        lines.append(f"  Price Action (24h Change)  {pa['btc'].get('emoji', '⚪')}")
        lines.append(f"  {'='*50}")
        for asset in ["BTC", "ETH"]:
            p = pa.get(asset)
            if p and p.get("change_24h") is not None:
                emoji = p.get("emoji", "⚪")
                zone = p.get("zone", "normal")
                lines.append(f"  {asset}: {p['change_24h']:+.2f}% ({zone}) {emoji}")

    # Volatility
    vol = details.get("volatility", {})
    if isinstance(vol, dict) and vol:
        lines.append(f"\n  {'='*50}")
        lines.append(f"  Volatility  {'🟡' if vol.get('BTC', {}).get('24h_vol') and vol['BTC']['24h_vol'] > 3 else '⚪'}")
        lines.append(f"  {'='*50}")
        for asset in ["BTC", "ETH"]:
            v = vol.get(asset, {})
            v24 = v.get("24h_vol_pct")
            if v24 is not None:
                bars = "▓" * int(v24) + "░" * max(0, 10 - int(v24))
                lines.append(f"  {asset} 24h: {v24:.2f}% |{bars}|")

    # Macro
    macro = details.get("macro", {})
    if isinstance(macro, dict):
        lines.append(f"\n  {'='*50}")
        lines.append(f"  Macro Overlay")
        lines.append(f"  {'='*50}")
        vix = macro.get("vix")
        dxy = macro.get("dxy")
        if vix:
            vix_emoji = "🔴" if vix > 30 else "🟡" if vix > 20 else "🟢"
            lines.append(f"  VIX: {vix:.2f} {vix_emoji}")
        if dxy:
            dxy_emoji = "🔴" if dxy > 108 else "🟢" if dxy < 102 else "🟡"
            lines.append(f"  DXY: {dxy:.2f} {dxy_emoji}")
        for interp in macro.get("interpretations", []):
            lines.append(f"  • {interp}")

    # Component scores
    scores = aggregate["scores"]
    lines.append(f"\n  {'='*50}")
    lines.append(f"  Component Scores")
    lines.append(f"  {'='*50}")
    label_map = {
        "funding_rate": "Funding Rate",
        "liquidations": "Liquidations",
        "fear_and_greed": "Fear & Greed",
        "price_action": "Price Action",
        "volatility": "Volatility",
        "macro_overlay": "Macro Context",
    }
    for key in sorted(scores.keys(), key=lambda k: scores[k], reverse=True):
        pct = scores[key]
        bar = "▓" * int(pct / 10) + "░" * (10 - int(pct / 10))
        w = SIGNAL_WEIGHTS[key]
        contribution = round(pct * w, 1)
        lines.append(f"  {label_map[key]:20s} {pct:4.0f}/100 (w:{w}) = {contribution:.1f}  |{bar}|")

    # Recommendation
    rec = aggregate["recommendation"]
    lines.append(f"\n{'='*70}")
    lines.append(f"  💡 RECOMMENDATION")
    lines.append(f"{'='*70}")
    lines.append(f"\n  Action: {rec['action']}")
    lines.append(f"  Confidence: {rec['confidence']}")
    lines.append(f"\n  Guide:")
    for line in rec["guide"].split(". "):
        if line:
            lines.append(f"  • {line.strip()}")

    lines.append("\n" + "=" * 70)
    lines.append("")

    return "\n".join(lines)


# ─── Main ─────────────────────────────────────────────────────────────────────

def run_scan(full: bool = False, output_json: bool = False) -> Dict:
    """Run the full scan pipeline."""
    t0 = time.time()

    # 1. Current prices
    current = get_btc_eth_current()

    # 2. Binance data (funding + liquidations)
    funding_btc = get_binance_funding_rate("BTCUSDT")
    funding_eth = get_binance_funding_rate("ETHUSDT")
    liq_btc = get_binance_liquidations("BTCUSDT")
    liq_eth = get_binance_liquidations("ETHUSDT")

    # Use BTC data as primary (more liquid, more reliable signals)
    funding = funding_btc or funding_eth
    liq = liq_btc or liq_eth

    # 3. Load price history from config
    try:
        with open("trading_config.json", "r") as f:
            config = json.load(f)
        price_history = config.get("price_history", {})
    except Exception:
        price_history = {}

    # 4. Optional: stablecoin supply + macro
    stable = get_stablecoin_supply() if full else None
    fg = get_fear_and_greed()  # always available, fast API
    vix = get_vix() if full else None
    dxy = get_dxy() if full else None
    macro = analyze_macro(vix, dxy, fg) if full else {}

    # 5. Run analysis
    pa = analyze_price_action(current, price_history)
    vol = analyze_volatility(price_history)
    aggregate = aggregate_score(funding, liq, pa, vol, macro, fg=fg)

    elapsed = time.time() - t0

    # Merge results
    result = {
        **aggregate,
        "current_prices": current,
        "stablecoin_supply": stable,
        "elapsed_seconds": round(elapsed, 2),
    }

    if output_json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(format_scan(result, current))

    return result


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Dip Signal Analyzer — real market microstructure signals for the trading bot",
    )
    parser.add_argument("--full", action="store_true", help="Include macro overlay (VIX, DXY)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--quick", action="store_true", help="Quick scan (no macro, faster)")
    args = parser.parse_args()

    # Check for legacy --full flag (same as --full)
    full = args.full

    result = run_scan(full=full, output_json=args.json)

    # Exit code: 0 = normal, 1 = opportunity detected
    score = result.get("composite_score", 0)
    if score >= 45:
        sys.exit(0)  # opportunity detected
    else:
        sys.exit(0)  # always exit 0 (this is informational, not automated)


if __name__ == "__main__":
    main()
