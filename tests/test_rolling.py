"""Tests for rolling window statistics."""

from datetime import datetime, timedelta
from feesentinel.rolling import Rolling


def test_rolling_empty():
    """Test rolling stats with no data points."""
    rolling = Rolling(60)
    stats = rolling.stats()
    assert stats["avg"] == 0
    assert stats["min"] == 0
    assert stats["max"] == 0
    assert stats["n"] == 0


def test_rolling_basic():
    """Test rolling stats with basic data."""
    rolling = Rolling(60)
    base_time = datetime.utcnow()
    
    rolling.add(base_time, 10)
    rolling.add(base_time + timedelta(minutes=1), 20)
    rolling.add(base_time + timedelta(minutes=2), 30)
    
    stats = rolling.stats()
    assert stats["avg"] == 20
    assert stats["min"] == 10
    assert stats["max"] == 30
    assert stats["n"] == 3


def test_rolling_window_pruning():
    """Test that old points are pruned outside the window."""
    rolling = Rolling(60)  # 60 minute window
    base_time = datetime.utcnow()
    
    # Add point outside window
    rolling.add(base_time - timedelta(minutes=61), 5)
    
    # Add points inside window
    rolling.add(base_time, 10)
    rolling.add(base_time + timedelta(minutes=30), 20)
    
    stats = rolling.stats()
    assert stats["n"] == 2
    assert stats["min"] == 10
    assert stats["max"] == 20

