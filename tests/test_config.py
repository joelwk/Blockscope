"""Tests for configuration loading."""

import os
import tempfile
import yaml
import pytest
from feesentinel.config import Config


def test_config_defaults():
    """Test that config loads with defaults when file is minimal."""
    config_data = {
        "rpc": {"url": "http://test:8332"},
        "polling": {"poll_secs": 30}
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config_data, f)
        temp_path = f.name
    
    try:
        config = Config(temp_path)
        assert config.rpc_url == "http://test:8332"
        assert config.poll_secs == 30
        assert config.rpc_user == "bitcoin"  # default
        assert config.rolling_window_mins == 60  # default
    finally:
        os.unlink(temp_path)


def test_config_env_overrides():
    """Test that environment variables override config values."""
    config_data = {
        "rpc": {"url": "http://original:8332", "user": "original"},
        "polling": {"poll_secs": 60}
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config_data, f)
        temp_path = f.name
    
    try:
        os.environ["FS_RPC_URL"] = "http://override:8332"
        os.environ["FS_POLL_SECS"] = "120"
        
        config = Config(temp_path)
        assert config.rpc_url == "http://override:8332"
        assert config.poll_secs == 120
        assert config.rpc_user == "original"  # not overridden
    finally:
        os.unlink(temp_path)
        if "FS_RPC_URL" in os.environ:
            del os.environ["FS_RPC_URL"]
        if "FS_POLL_SECS" in os.environ:
            del os.environ["FS_POLL_SECS"]


