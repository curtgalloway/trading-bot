from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List

from .models import TradeSignal


def load_signals(path: str | Path) -> List[TradeSignal]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    items = raw.get("signals", raw) if isinstance(raw, dict) else raw
    signals: list[TradeSignal] = []

    for item in items:
        signals.append(
            TradeSignal(
                symbol=item["symbol"],
                action=item["action"],
                confidence=float(item.get("confidence", 0.5)),
                cluster_size=int(item.get("cluster_size", 2)),
                source=item.get("source", "congressional-trades"),
                source_date=item.get("source_date", ""),
                horizon_days=int(item.get("horizon_days", 30)),
                reason=item.get("reason", ""),
                metadata=item.get("metadata", {}),
            )
        )

    return signals

