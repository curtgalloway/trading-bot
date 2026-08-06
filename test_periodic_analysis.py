#!/usr/bin/env python3
"""Test the periodic analysis feature"""

from trading_monitor import TradingMonitor

print("Initializing trading monitor...")
monitor = TradingMonitor()

print("\nChecking if analysis should run...")
should_run = monitor.should_run_analysis()
print(f"Should run: {should_run}")

if should_run:
    print("\nRunning periodic analysis...")
    monitor.run_periodic_analysis()
    print("\n✅ Analysis complete! Check trading_analysis.log for results")
else:
    print("\n⏭️  Skipping analysis (conditions not met)")
