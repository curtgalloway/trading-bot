# Periodic Trigger Analysis

## Overview
The trading bot now includes automatic periodic analysis of trading performance to recommend trigger optimizations.

## How It Works

### Automatic Analysis
- Runs automatically during normal monitoring cycles
- Frequency: Every 7 days (configurable)
- Minimum positions: 5 active positions required
- Non-intrusive: Only recommends changes, never applies them automatically

### What It Analyzes
- Portfolio performance (P&L, win rate, max gain/loss)
- Current vs optimal trigger values
- Position statistics and trends
- Significant deviations (≥2% difference triggers alerts)

### Configuration

Located in `trading_config.json`:

```json
{
  "analysis": {
    "enabled": true,                    // Enable/disable periodic analysis
    "frequency_days": 7,                // Days between analyses
    "min_positions_for_analysis": 5,   // Minimum positions needed
    "last_analysis": "2026-02-05T09:44:05.180890"  // Auto-updated
  }
}
```

### Output

**Analysis Log**: `trading_analysis.log`
- Detailed analysis results
- Current vs suggested triggers
- Performance statistics
- Recommendations with rationale

**Main Log**: `trading_monitor.log`
- Notification when analysis runs
- Alert when significant changes recommended

**Console Output**: During monitoring cycles
- Alert banner when changes recommended
- Directs you to review analysis log

## Usage

### Manual Analysis
Run analysis on demand:
```bash
python3 test_periodic_analysis.py
```

Or use the existing optimizer:
```bash
python3 optimize_triggers.py
```

### Review Recommendations
```bash
tail -50 trading_analysis.log
```

### Disable Analysis
Edit `trading_config.json`:
```json
{
  "analysis": {
    "enabled": false
  }
}
```

## Example Output

```
2026-02-05 09:44:05 - Positions: 22 total, 2 profitable (9.1%)
2026-02-05 09:44:05 - Portfolio P&L: -22.56%
2026-02-05 09:44:05 - Max Gain: +33.64%, Max Loss: -75.23%, Avg: -18.89%

CURRENT TRIGGERS:
  Buy Dip: 12%
  Profit Target: 20%
  Final Profit: 28%
  Stop Loss: 12%

SUGGESTED TRIGGERS:
  Buy Dip: 12%
  Profit Target: 20%
  Final Profit: 30%
  Stop Loss: 15%

⚠️  SIGNIFICANT CHANGES RECOMMENDED:
  • final_profit_target_percent: 28% → 30%
  • stop_loss_percent: 12% → 15%
```

## Safety Features

1. **Minimum Sample Size**: Requires 5+ active positions
2. **Rate Limiting**: Max once per 7 days (configurable)
3. **Bounded Suggestions**: Triggers stay within reasonable ranges
4. **Manual Approval**: You must manually apply changes
5. **Clear Logging**: All analysis recorded for review

## When to Apply Recommendations

Consider applying when:
- ✅ Multiple cycles show consistent suggestions
- ✅ Current triggers clearly underperforming
- ✅ Market conditions align with suggestion rationale
- ✅ You understand the impact of changes

Be cautious when:
- ⚠️ Based on small sample size (near minimum)
- ⚠️ During volatile market conditions
- ⚠️ Suggestions conflict with your strategy
- ⚠️ First-time recommendation (wait for confirmation)

## Integration with Monitor

The analysis runs automatically as part of `trading_monitor.py`:
- Checks conditions at end of each monitoring cycle
- Runs silently if no changes needed
- Alerts prominently when recommendations available
- Minimal performance impact (only runs when needed)
