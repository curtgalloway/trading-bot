# Trading Bot — Rulebook

> **Current phase:** Phase 5 (Nov 13, 2026)
> **Status:** Live Trading (not dry-run)
> **Source:** `~/prog/trading-bot/trading_config.json` + code review

---

## Configuration Snapshot

| Setting | Value |
|---------|-------|
| Budget | €50 (~$305 USDC real balance on Coinbase) |
| Min buffer | €5 ($5) — halts trading if below this |
| Check interval | Every 15 minutes |
| Buy assets | BTC, ETH only |
| Buy amount | €10 per buy |
| Buy cooldown | 24 hours per asset |
| Taker fee | 1.2% |
| Maker fee | 0.6% |
| Round-trip fee drag | ~2.4% per full trade |

---

## SELL Rules

### Two-Stage Profit Exit

| Trigger | Action | Rationale |
|---------|--------|-----------|
| **+25% gain** | Sell 50% of position | Lock in gains, reduce risk exposure |
| **+40% gain** | Sell remaining 50% | Full exit, capture additional upside |

**How it works:** On first hit, `total_sold` is tracked and the position shrinks. The remaining half stays open until +40% or stop-loss.

### Stop-Loss

| Trigger | Action | Rationale |
|---------|--------|-----------|
| **-20% loss** | Sell 100% of position | Wide enough to survive normal crypto drawdowns (10-15% daily swings) |

**Breakeven math:** With -20% stop and +25% target, you only need a **29% win rate** to break even (including 2.4% fee drag).

**Evolution:** -10% (Oct) → -15% (Aug-Feb) → **-20% (Nov 13, current)**. The -10% was a money-printing-loss-machine — normal volatility stopped you out before profit could materialize.

---

## BUY Rules (Three Entry Signals)

### A) Buy-the-Dip (Primary)

1. Track 7-day rolling high per asset
2. If current price ≥12% below 7-day high → buy €10
3. Skips assets already held (no duplicate)
4. 24-hour cooldown per asset

**Reference:** `get_7day_high()` in `trading_monitor.py`

### B) Re-Entry Logic

- When a sold position has a 30-day expiry window
- If price drops 10-15% below the sale price → buy €10
- Captures mean reversion on positions you've already taken profit on

### C) Time-Fallback Guard (Nov 13 addition)

| Component | Value |
|-----------|-------|
| max_idle_days | 30 |
| fallback_amount | €10 |
| fallback_assets | BTC, ETH |
| require_dip | **true** |
| min_dip_percent | 10 |

Only fires if idle 30+ days **AND** price is ≥10% below 7-day high. Previously bought at market price — the main cause of recent losses.

---

## Active Positions (Nov 17, 2026)

| Asset | Entry Price | Amount | Entry Date | Entry Method |
|-------|------------|--------|------------|-------------|
| ETH | $1,749.45 | 0.00629 | Nov 14 | Dip buy |
| BTC | $62,646.08 | 0.000176 | Nov 15 | Dip buy |

Both bought on dip entries, both still in position.

---

## Auto-Analysis

- Runs every **7 days** (requires 5+ positions)
- Analyzes: P&L, win rate, max gain/loss, avg P&L
- Suggests trigger changes within bounded ranges (stop 5-25%, buy dip 5-20%, profit 10-50%)
- **Never auto-applies** — writes to `trading_analysis.log` for manual review
- Console banner if ≥2% change recommended

**Current status:** Never been run (not enough positions yet).

---

## Strategy Evolution Timeline

| Phase | Date | Key Changes |
|-------|------|-------------|
| 1 | 2024-2025 | 12 altcoins, loose triggers, -75% losses |
| 2 | Feb 2, 2026 | BTC/ETH only, tighter triggers |
| 3 | Aug 2026 | Congressional stock bot (dry-run, never shipped) |
| 4 | Aug 31, 2026 | Fixed idle bot: time-fallback added, real USDC balance |
| 5 | **Nov 13, 2026** | **-20% stop, +25%/+40% targets, dip-only fallback** |

---

## On-Pi Tooling

| Script | What it does |
|--------|-------------|
| `check_dip_signals.py` | Quick keyword-based news scan for crash signals |
| `dip_signal_analyzer.py` | Sophisticated: funding rates, liquidations, fear/greed, VIX. Run with `--full` |
| `analyze_performance.py` | Full P&L report with missed opportunity tracking |
| `optimize_triggers.py` | Manual trigger optimizer with backtesting |
| `backtest.py` | Historical backtesting |

---

## Related

- [[Trading Bot Strategy]] — Detailed parameter rationale and evolution
- [[Trading Bot README]] — Project overview
- [[Trading Bot Performance]] — P&L and metrics
- [[Trading Bot Architecture]] — Technical design
- [[Trading Bot Auto-Analysis]] — Optimization system
- [[Trading Bot Issues]] — Known problems
