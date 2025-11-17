"""Tests for runner consolidation logic with bucket policies."""

import os
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from feesentinel.buckets import FEE_BUCKETS, FEE_POLICIES, FeeBucket
from feesentinel.runner import should_prepare_consolidation, get_psbt_cooldown_secs, _last_psbt


def test_should_prepare_consolidation_policy_check():
    """Test that should_prepare_consolidation respects bucket policies."""
    # Reset cooldown state
    _last_psbt["ts"] = datetime.min
    
    # Buckets that allow consolidation
    free_bucket = FEE_BUCKETS[1]  # free
    cheap_bucket = FEE_BUCKETS[2]  # cheap
    
    # Buckets that don't allow consolidation
    zero_bucket = FEE_BUCKETS[0]  # zero
    normal_bucket = FEE_BUCKETS[3]  # normal
    busy_bucket = FEE_BUCKETS[4]  # busy
    
    # Should return True for free/cheap (with cooldown satisfied)
    assert should_prepare_consolidation(free_bucket, 0) is True
    _last_psbt["ts"] = datetime.min  # Reset
    assert should_prepare_consolidation(cheap_bucket, 0) is True
    
    # Should return False for buckets that don't allow consolidation
    _last_psbt["ts"] = datetime.min  # Reset
    assert should_prepare_consolidation(zero_bucket, 0) is False
    assert should_prepare_consolidation(normal_bucket, 0) is False
    assert should_prepare_consolidation(busy_bucket, 0) is False


def test_should_prepare_consolidation_cooldown():
    """Test that should_prepare_consolidation respects cooldown period."""
    # Reset cooldown state
    _last_psbt["ts"] = datetime.min
    
    free_bucket = FEE_BUCKETS[1]  # free
    
    # First call should succeed (cooldown satisfied)
    assert should_prepare_consolidation(free_bucket, 3600) is True
    
    # Second call immediately after should fail (cooldown not satisfied)
    assert should_prepare_consolidation(free_bucket, 3600) is False
    
    # After cooldown period, should succeed again
    _last_psbt["ts"] = datetime.utcnow() - timedelta(seconds=3601)
    assert should_prepare_consolidation(free_bucket, 3600) is True


def test_should_prepare_consolidation_cooldown_boundary():
    """Test cooldown boundary conditions."""
    _last_psbt["ts"] = datetime.min
    
    free_bucket = FEE_BUCKETS[1]  # free
    cooldown_secs = 100
    
    # First call succeeds
    assert should_prepare_consolidation(free_bucket, cooldown_secs) is True
    
    # Just before cooldown boundary should fail
    _last_psbt["ts"] = datetime.utcnow() - timedelta(seconds=cooldown_secs - 1)
    assert should_prepare_consolidation(free_bucket, cooldown_secs) is False
    
    # Exactly at cooldown boundary should succeed (>= cooldown_secs)
    _last_psbt["ts"] = datetime.utcnow() - timedelta(seconds=cooldown_secs)
    assert should_prepare_consolidation(free_bucket, cooldown_secs) is True
    
    # Just past cooldown boundary should succeed
    _last_psbt["ts"] = datetime.utcnow() - timedelta(seconds=cooldown_secs + 1)
    assert should_prepare_consolidation(free_bucket, cooldown_secs) is True


def test_get_psbt_cooldown_secs_from_config():
    """Test that get_psbt_cooldown_secs reads from config."""
    from feesentinel.config import Config
    
    # Create a mock config with custom cooldown
    config = MagicMock()
    config.psbt_cooldown_secs = 7200
    
    assert get_psbt_cooldown_secs(config) == 7200


def test_get_psbt_cooldown_secs_from_env():
    """Test that get_psbt_cooldown_secs reads from environment variable."""
    with patch.dict(os.environ, {"FS_PSBT_COOLDOWN_SECS": "1800"}):
        assert get_psbt_cooldown_secs(None) == 1800


def test_get_psbt_cooldown_secs_default():
    """Test that get_psbt_cooldown_secs uses default when no config/env."""
    with patch.dict(os.environ, {}, clear=True):
        # Remove FS_PSBT_COOLDOWN_SECS if it exists
        os.environ.pop("FS_PSBT_COOLDOWN_SECS", None)
        assert get_psbt_cooldown_secs(None) == 3600


def test_should_prepare_consolidation_updates_timestamp():
    """Test that should_prepare_consolidation updates timestamp on success."""
    _last_psbt["ts"] = datetime.min
    
    free_bucket = FEE_BUCKETS[1]  # free
    initial_time = datetime.utcnow()
    
    # Call should succeed and update timestamp
    result = should_prepare_consolidation(free_bucket, 0)
    assert result is True
    
    # Timestamp should be updated to recent time
    assert _last_psbt["ts"] > datetime.min
    assert _last_psbt["ts"] >= initial_time - timedelta(seconds=1)


def test_should_prepare_consolidation_does_not_update_timestamp_on_failure():
    """Test that timestamp is not updated when consolidation is not allowed."""
    original_ts = datetime.utcnow() - timedelta(days=1)
    _last_psbt["ts"] = original_ts
    
    normal_bucket = FEE_BUCKETS[3]  # normal (consolidate_ok=False)
    
    # Call should fail and not update timestamp
    result = should_prepare_consolidation(normal_bucket, 0)
    assert result is False
    
    # Timestamp should remain unchanged
    assert _last_psbt["ts"] == original_ts

