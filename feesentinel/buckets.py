"""Fee bucket classification for Bitcoin fee monitoring."""

from dataclasses import dataclass
from .constants import EXTREME_BUCKET_MAX_SATVB


@dataclass(frozen=True)
class FeeBucket:
    """Represents a fee bucket with name, label, range, and severity."""
    name: str           # short id, e.g., "normal"
    label: str          # human label, e.g., "Normal fee market"
    min_satvb: int      # inclusive
    max_satvb: int      # inclusive
    severity: int       # 0 = lowest, monotone across buckets


FEE_BUCKETS = [
    FeeBucket(
        name="zero",
        label="No reliable fee data",
        min_satvb=0,
        max_satvb=0,
        severity=0,
    ),
    FeeBucket(
        name="free",
        label="Free blocks / near-empty mempool",
        min_satvb=1,
        max_satvb=1,
        severity=1,
    ),
    FeeBucket(
        name="cheap",
        label="Very low fees",
        min_satvb=2,
        max_satvb=5,
        severity=2,
    ),
    FeeBucket(
        name="normal",
        label="Normal fee market",
        min_satvb=6,
        max_satvb=15,
        severity=3,
    ),
    FeeBucket(
        name="busy",
        label="Busy but reasonable",
        min_satvb=16,
        max_satvb=40,
        severity=4,
    ),
    FeeBucket(
        name="high",
        label="High congestion",
        min_satvb=41,
        max_satvb=100,
        severity=5,
    ),
    FeeBucket(
        name="peak",
        label="Peak mania",
        min_satvb=101,
        max_satvb=250,
        severity=6,
    ),
    FeeBucket(
        name="extreme",
        label="Extreme blockspace stress",
        min_satvb=251,
        max_satvb=EXTREME_BUCKET_MAX_SATVB,  # practical cap
        severity=7,
    ),
]


def classify_fee_bucket(p50_satvb: int) -> FeeBucket:
    """
    Map p50 sat/vB into a named fee bucket.
    Falls back to the highest bucket if p50 exceeds all configured ranges.
    
    Args:
        p50_satvb: p50 fee in sat/vB
        
    Returns:
        FeeBucket instance matching the fee value
    """
    for bucket in FEE_BUCKETS:
        if bucket.min_satvb <= p50_satvb <= bucket.max_satvb:
            return bucket
    # If p50 exceeds all ranges, return the highest bucket
    return FEE_BUCKETS[-1]


# ---------- Policy hints per bucket ----------

FEE_POLICIES = {
    "zero": {
        "consolidate_ok": False,
        "broadcast_normal": False,
        "note": "No reliable fee data; avoid automated actions.",
    },
    "free": {
        "consolidate_ok": True,
        "broadcast_normal": True,
        "note": "Prime time for UTXO consolidation and low-priority sends.",
    },
    "cheap": {
        "consolidate_ok": True,
        "broadcast_normal": True,
        "note": "Very low fees; safe for consolidation, batching, and routine TX.",
    },
    "normal": {
        "consolidate_ok": False,
        "broadcast_normal": True,
        "note": "Standard fee market; routine TX fine, defer large consolidations.",
    },
    "busy": {
        "consolidate_ok": False,
        "broadcast_normal": True,
        "note": "Busy; consider RBF, batching, and delaying non-urgent activity.",
    },
    "high": {
        "consolidate_ok": False,
        "broadcast_normal": True,
        "note": "High congestion; prioritize only important payments.",
    },
    "peak": {
        "consolidate_ok": False,
        "broadcast_normal": False,
        "note": "Peak mania; only critical TXs, everything else waits.",
    },
    "extreme": {
        "consolidate_ok": False,
        "broadcast_normal": False,
        "note": "Extreme stress; disable automation & consolidation entirely.",
    },
}
