"""Rolling window statistics for fee monitoring."""

from datetime import datetime, timedelta
from typing import Dict, List, Tuple


class Rolling:
    """Rolling window statistics calculator."""
    
    def __init__(self, minutes: int):
        """
        Initialize rolling window.
        
        Args:
            minutes: Window size in minutes
        """
        self.minutes = minutes
        self.points: List[Tuple[datetime, int]] = []  # list[(ts, p50_satvb)]
    
    def add(self, ts: datetime, p50: int):
        """
        Add a data point and prune old points outside the window.
        
        Args:
            ts: Timestamp
            p50: p50 fee value in sat/vB
        """
        self.points.append((ts, p50))
        cutoff = ts - timedelta(minutes=self.minutes)
        self.points = [(t, v) for (t, v) in self.points if t >= cutoff]
    
    def stats(self) -> Dict[str, int]:
        """
        Calculate rolling statistics.
        
        Returns:
            Dictionary with avg, min, max, and n (count) keys
        """
        vals = [v for _, v in self.points]
        if not vals:
            return {"avg": 0, "min": 0, "max": 0, "n": 0}
        
        return {
            "avg": int(round(sum(vals) / len(vals))),
            "min": min(vals),
            "max": max(vals),
            "n": len(vals)
        }

