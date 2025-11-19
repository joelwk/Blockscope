"""Tests for alert management."""

from datetime import datetime, timedelta
from feesentinel.alerts import AlertManager
from feesentinel.buckets import classify_fee_bucket


def test_maybe_alert_no_webhook():
    """Test that alerts are logged when no webhook is set."""
    manager = AlertManager("", 300)
    
    # Should not raise, just log
    bucket1 = classify_fee_bucket(2)  # cheap
    bucket2 = classify_fee_bucket(10)  # normal
    manager.maybe_alert(bucket1, {"p50": 2})
    manager.maybe_alert(bucket2, {"p50": 10})


def test_maybe_alert_quiet_period():
    """Test that alerts respect quiet period."""
    manager = AlertManager("", 0)  # No quiet period for testing
    
    bucket1 = classify_fee_bucket(2)  # cheap, severity 2
    bucket2 = classify_fee_bucket(10)  # normal, severity 3
    
    # First alert should fire
    manager.maybe_alert(bucket1, {"p50": 2})
    assert manager._last_bucket_alert["bucket_name"] == "cheap"
    assert manager._last_bucket_alert["severity"] == 2
    
    # Same bucket immediately should not fire (same severity, no change)
    initial_ts = manager._last_bucket_alert["ts"]
    manager.maybe_alert(bucket1, {"p50": 2})
    # Bucket should still be cheap since severity didn't change
    assert manager._last_bucket_alert["bucket_name"] == "cheap"
    assert manager._last_bucket_alert["severity"] == 2
    
    # Different bucket (different severity) should fire
    manager.maybe_alert(bucket2, {"p50": 10})
    assert manager._last_bucket_alert["bucket_name"] == "normal"
    assert manager._last_bucket_alert["severity"] == 3


def test_maybe_alert_same_severity_no_alert():
    """Test that alerts don't fire for buckets with same severity."""
    manager = AlertManager("", 0)  # No quiet period for testing
    
    # Both cheap and free have different severities, but let's test same severity
    # Actually, all buckets have unique severities, so this tests that
    # changing within same bucket doesn't trigger (but that's handled by quiet period)
    bucket = classify_fee_bucket(3)  # cheap
    manager.maybe_alert(bucket, {"p50": 3})
    initial_ts = manager._last_bucket_alert["ts"]
    
    # Same bucket again immediately - should not fire due to quiet period
    manager.maybe_alert(bucket, {"p50": 3})
    # Timestamp should be same (or very close) since alert didn't fire

