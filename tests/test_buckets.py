"""Tests for fee bucket classification."""

from feesentinel.buckets import classify_fee_bucket, FEE_BUCKETS, FEE_POLICIES


def test_classify_zero():
    """Test zero bucket classification."""
    bucket = classify_fee_bucket(0)
    assert bucket.name == "zero"
    assert bucket.severity == 0


def test_classify_free():
    """Test free bucket classification."""
    bucket = classify_fee_bucket(1)
    assert bucket.name == "free"
    assert bucket.severity == 1


def test_classify_cheap():
    """Test cheap bucket classification."""
    assert classify_fee_bucket(2).name == "cheap"
    assert classify_fee_bucket(3).name == "cheap"
    assert classify_fee_bucket(4).name == "cheap"
    assert classify_fee_bucket(5).name == "cheap"


def test_classify_normal():
    """Test normal bucket classification."""
    assert classify_fee_bucket(6).name == "normal"
    assert classify_fee_bucket(10).name == "normal"
    assert classify_fee_bucket(15).name == "normal"


def test_classify_busy():
    """Test busy bucket classification."""
    assert classify_fee_bucket(16).name == "busy"
    assert classify_fee_bucket(25).name == "busy"
    assert classify_fee_bucket(40).name == "busy"


def test_classify_high():
    """Test high bucket classification."""
    assert classify_fee_bucket(41).name == "high"
    assert classify_fee_bucket(75).name == "high"
    assert classify_fee_bucket(100).name == "high"


def test_classify_peak():
    """Test peak bucket classification."""
    assert classify_fee_bucket(101).name == "peak"
    assert classify_fee_bucket(200).name == "peak"
    assert classify_fee_bucket(250).name == "peak"


def test_classify_extreme():
    """Test extreme bucket classification."""
    assert classify_fee_bucket(251).name == "extreme"
    assert classify_fee_bucket(500).name == "extreme"
    assert classify_fee_bucket(1000).name == "extreme"
    assert classify_fee_bucket(10000).name == "extreme"
    # Values exceeding max should still return extreme
    assert classify_fee_bucket(50000).name == "extreme"


def test_bucket_boundaries():
    """Test bucket boundary conditions."""
    # Test exact boundaries
    assert classify_fee_bucket(0).name == "zero"
    assert classify_fee_bucket(1).name == "free"
    assert classify_fee_bucket(2).name == "cheap"
    assert classify_fee_bucket(5).name == "cheap"
    assert classify_fee_bucket(6).name == "normal"
    assert classify_fee_bucket(15).name == "normal"
    assert classify_fee_bucket(16).name == "busy"
    assert classify_fee_bucket(40).name == "busy"
    assert classify_fee_bucket(41).name == "high"
    assert classify_fee_bucket(100).name == "high"
    assert classify_fee_bucket(101).name == "peak"
    assert classify_fee_bucket(250).name == "peak"
    assert classify_fee_bucket(251).name == "extreme"


def test_bucket_severity_monotonicity():
    """Test that bucket severity increases monotonically."""
    severities = [bucket.severity for bucket in FEE_BUCKETS]
    assert severities == sorted(severities)
    assert len(set(severities)) == len(severities)  # All unique


def test_fee_policies_completeness():
    """Test that FEE_POLICIES has entries for all buckets."""
    bucket_names = {bucket.name for bucket in FEE_BUCKETS}
    policy_names = set(FEE_POLICIES.keys())
    assert bucket_names == policy_names, "FEE_POLICIES missing buckets or has extra entries"


def test_fee_policies_structure():
    """Test that each policy has required fields."""
    required_fields = {"consolidate_ok", "broadcast_normal", "note"}
    for bucket_name, policy in FEE_POLICIES.items():
        assert isinstance(policy, dict), f"Policy for {bucket_name} must be a dict"
        for field in required_fields:
            assert field in policy, f"Policy for {bucket_name} missing field: {field}"
        assert isinstance(policy["consolidate_ok"], bool), f"consolidate_ok for {bucket_name} must be bool"
        assert isinstance(policy["broadcast_normal"], bool), f"broadcast_normal for {bucket_name} must be bool"
        assert isinstance(policy["note"], str), f"note for {bucket_name} must be str"
        assert len(policy["note"]) > 0, f"note for {bucket_name} must not be empty"


def test_fee_policies_consolidation_rules():
    """Test that consolidation policies match expected behavior."""
    # free and cheap should allow consolidation
    assert FEE_POLICIES["free"]["consolidate_ok"] is True
    assert FEE_POLICIES["cheap"]["consolidate_ok"] is True
    
    # zero, normal, busy, high, peak, extreme should not allow consolidation
    assert FEE_POLICIES["zero"]["consolidate_ok"] is False
    assert FEE_POLICIES["normal"]["consolidate_ok"] is False
    assert FEE_POLICIES["busy"]["consolidate_ok"] is False
    assert FEE_POLICIES["high"]["consolidate_ok"] is False
    assert FEE_POLICIES["peak"]["consolidate_ok"] is False
    assert FEE_POLICIES["extreme"]["consolidate_ok"] is False


def test_fee_policies_broadcast_rules():
    """Test that broadcast policies match expected behavior."""
    # zero, peak, extreme should not allow normal broadcast
    assert FEE_POLICIES["zero"]["broadcast_normal"] is False
    assert FEE_POLICIES["peak"]["broadcast_normal"] is False
    assert FEE_POLICIES["extreme"]["broadcast_normal"] is False
    
    # All others should allow normal broadcast
    assert FEE_POLICIES["free"]["broadcast_normal"] is True
    assert FEE_POLICIES["cheap"]["broadcast_normal"] is True
    assert FEE_POLICIES["normal"]["broadcast_normal"] is True
    assert FEE_POLICIES["busy"]["broadcast_normal"] is True
    assert FEE_POLICIES["high"]["broadcast_normal"] is True

