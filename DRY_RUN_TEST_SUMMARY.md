# Congressional Stock Bot - Dry Run Test Summary

**Date:** 2026-08-05  
**Status:** ✅ PASSED

## Quick Results

### Trade 1: MSFT BUY
- **Signal:** 4 senators buying (strong cluster)
- **Confidence:** 82%
- **Position:** €984 (1.97% of portfolio)
- **Risk:** €29.52 (3% stop loss)
- **Reward:** €49.20 (5% take profit)
- **Risk/Reward:** 1.66:1

### Trade 2: JNJ SELL
- **Signal:** 3 senators selling (moderate cluster)
- **Confidence:** 78%
- **Position:** €1,219 (2.44% of portfolio)
- **Risk:** €36.57 (3% stop loss)
- **Reward:** €60.95 (5% take profit)
- **Risk/Reward:** 1.67:1

## Validation

✅ All tests passed:
- Position sizing: Both ~2% of portfolio
- Risk limits: Max €1,000 per trade (2% rule)
- Safety caps: Both under 10% max position
- Multipliers: Confidence, action, cluster all applied correctly
- Combined risk: €66 (0.13% of €50K portfolio)

## Next Steps

1. Test IBKR connection (Option 2)
2. Get real congressional signals
3. Paper trade with small positions
4. Track performance over time

## Command

```bash
python3 run_congressional_bot.py --signals congressional_signals.example.json
```

Full analysis: See Obsidian note "Congressional Bot Dry Run Test 2026-08-05"
