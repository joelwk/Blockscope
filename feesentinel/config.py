"""Configuration loading and validation for Blockscope."""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, List


class Config:
    """Configuration container with environment variable overrides."""
    
    def __init__(self, config_path: str = None, create_if_missing: bool = True):
        """
        Load configuration from YAML file with environment variable overrides.
        
        Configuration precedence (highest to lowest):
        1. Environment variables (FS_* prefix)
        2. config.local.yaml (if exists, local overrides)
        3. config.yaml (main config file)
        4. Default values
        
        Args:
            config_path: Path to config.yaml. If None, searches for config.yaml
                        in current directory and parent directories.
            create_if_missing: If True and config_path is None, create default config
                              if not found. If config_path is explicitly provided,
                              this is ignored (file must exist).
        """
        if config_path is None:
            config_path = self._find_config_file()
            config_file_path = Path(config_path)
            # Only create default if auto-discovered and missing
            if create_if_missing and not config_file_path.exists():
                self._create_default_config(config_path)
        else:
            # Explicit path provided - must exist
            config_file_path = Path(config_path)
            if not config_file_path.exists():
                raise FileNotFoundError(f"Config file not found: {config_path}")
        
        # Load main config file
        with open(config_path, 'r') as f:
            self._raw = yaml.safe_load(f) or {}
        
        # Load local overrides if config.local.yaml exists (gitignored, for secrets)
        config_dir = Path(config_path).parent
        local_config_path = config_dir / "config.local.yaml"
        if local_config_path.exists():
            with open(local_config_path, 'r') as f:
                local_config = yaml.safe_load(f) or {}
                # Deep merge local config over main config
                self._deep_merge(self._raw, local_config)
        
        # Apply environment variable overrides (highest precedence)
        self._apply_env_overrides()
        
        # Validate and normalize
        self._validate()
    
    def _find_config_file(self) -> str:
        """Find config.yaml in current directory or parents."""
        current = Path.cwd()
        for path in [current] + list(current.parents):
            config_file = path / "config.yaml"
            if config_file.exists():
                return str(config_file)
        # Default to current directory if not found
        return str(current / "config.yaml")
    
    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> None:
        """Recursively merge override dict into base dict."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
    
    def _create_default_config(self, path: str):
        """Create a default config.yaml file."""
        default_config = {
            "rpc": {
                "url": "http://127.0.0.1:8332",
                "user": "bitcoin",
                "password": ""
            },
            "polling": {
                "poll_secs": 60,
                "rolling_window_mins": 60
            },
            "alerts": {
                "webhook_url": "",
                "min_change_secs": 300
            },
            "spike_detection": {
                "enabled": True,
                "spike_pct": 35,
                "min_alert_satvb": 15,
                "cooldown_minutes": 20,
                "adjustment_rules": {
                    "target_sat_vb_floor": 12,
                    "bump_pct_if_queue_backlog": 20,
                    "drop_pct_if_clearing_fast": 15
                }
            },
            "consolidation": {
                "label": "feesentinel",
                "min_utxo_sats": 546,
                "max_inputs": 50,
                "target_address": "",
                "min_trigger_satvb": 5,
                "psbt_cooldown_secs": 3600
            },
            "logging": {
                "level": "INFO",
                "logfile": "",
                "log_dir": "logs",
                "console_level": "INFO",
                "rotation": {
                    "max_bytes": 10485760,
                    "backup_count": 30,
                    "when": "midnight"
                }
            },
            "event_watcher": {
                "enabled": False,
                "poll_interval_secs": 10,
                "start_height": None,
                "max_reorg_depth": 6,
                "filters": {
                    "treasury": {
                        "enabled": False,
                        "addresses": [],
                        "famous_addresses": [],
                        "clusters": [],
                        "address_files": [],
                        "watch_inputs": True,
                        "watch_outputs": True
                    },
                    "ordinals": {
                        "enabled": False,
                        "detect_inscriptions": True,
                        "hotspots": []
                    },
                    "covenants": {
                        "enabled": False,
                        "patterns": []
                    }
                },
                "events": {
                    "webhook_url": "",
                    "webhook_urls": [],
                    "retry_attempts": 3,
                    "retry_backoff_secs": 5
                },
                "state": {
                    "backend": "sqlite",
                    "db_path": "state/eventwatcher.db",
                    "json_path": "state/eventwatcher.json"
                },
                "metrics": {
                    "enabled": True,
                    "log_interval_secs": 300
                }
            },
            "structured_output": {
                "enabled": False,
                "base_dir": "logs/structured",
                "events_filename": "events.jsonl",
                "blocks_filename": "blocks.jsonl",
                "fee_alerts_filename": "fee_alerts.jsonl",
                "fee_snapshots_filename": "fee_snapshots.jsonl",
            }
        }
        with open(path, 'w') as f:
            yaml.dump(default_config, f, default_flow_style=False, sort_keys=False)
    
    def _apply_env_overrides(self):
        """Apply environment variable overrides using FS_ prefix."""
        # RPC settings
        if os.getenv("FS_RPC_URL"):
            self._raw.setdefault("rpc", {})["url"] = os.getenv("FS_RPC_URL")
        if os.getenv("FS_RPC_USER"):
            self._raw.setdefault("rpc", {})["user"] = os.getenv("FS_RPC_USER")
        if os.getenv("FS_RPC_PASS"):
            self._raw.setdefault("rpc", {})["password"] = os.getenv("FS_RPC_PASS")
        
        # Polling settings
        if os.getenv("FS_POLL_SECS"):
            self._raw.setdefault("polling", {})["poll_secs"] = int(os.getenv("FS_POLL_SECS"))
        if os.getenv("FS_ROLLING_WINDOW_MINS"):
            self._raw.setdefault("polling", {})["rolling_window_mins"] = int(os.getenv("FS_ROLLING_WINDOW_MINS"))
        
        # Alert settings
        if os.getenv("FS_ALERT_WEBHOOK"):
            self._raw.setdefault("alerts", {})["webhook_url"] = os.getenv("FS_ALERT_WEBHOOK")
        if os.getenv("FS_ALERT_MIN_CHANGE_SECS"):
            self._raw.setdefault("alerts", {})["min_change_secs"] = int(os.getenv("FS_ALERT_MIN_CHANGE_SECS"))
        
        # Spike detection settings
        if os.getenv("FS_SPIKE_ENABLED"):
            self._raw.setdefault("spike_detection", {})["enabled"] = os.getenv("FS_SPIKE_ENABLED").lower() == "true"
        if os.getenv("FS_SPIKE_PCT"):
            self._raw.setdefault("spike_detection", {})["spike_pct"] = int(os.getenv("FS_SPIKE_PCT"))
        if os.getenv("FS_SPIKE_MIN_ALERT_SATVB"):
            self._raw.setdefault("spike_detection", {})["min_alert_satvb"] = int(os.getenv("FS_SPIKE_MIN_ALERT_SATVB"))
        if os.getenv("FS_SPIKE_COOLDOWN_MINS"):
            self._raw.setdefault("spike_detection", {})["cooldown_minutes"] = int(os.getenv("FS_SPIKE_COOLDOWN_MINS"))
        
        # Consolidation settings
        if os.getenv("FS_CONSOLIDATE_LABEL"):
            self._raw.setdefault("consolidation", {})["label"] = os.getenv("FS_CONSOLIDATE_LABEL")
        if os.getenv("FS_CONSOLIDATE_MIN_UTXO_SATS"):
            self._raw.setdefault("consolidation", {})["min_utxo_sats"] = int(os.getenv("FS_CONSOLIDATE_MIN_UTXO_SATS"))
        if os.getenv("FS_CONSOLIDATE_MAX_INPUTS"):
            self._raw.setdefault("consolidation", {})["max_inputs"] = int(os.getenv("FS_CONSOLIDATE_MAX_INPUTS"))
        if os.getenv("FS_CONSOLIDATE_TARGET_ADDR"):
            self._raw.setdefault("consolidation", {})["target_address"] = os.getenv("FS_CONSOLIDATE_TARGET_ADDR")
        if os.getenv("FS_CONSOLIDATE_MIN_TRIGGER_SATVB"):
            self._raw.setdefault("consolidation", {})["min_trigger_satvb"] = int(os.getenv("FS_CONSOLIDATE_MIN_TRIGGER_SATVB"))
        if os.getenv("FS_PSBT_COOLDOWN_SECS"):
            self._raw.setdefault("consolidation", {})["psbt_cooldown_secs"] = int(os.getenv("FS_PSBT_COOLDOWN_SECS"))
        
        # Logging settings
        if os.getenv("FS_LOG_DIR"):
            self._raw.setdefault("logging", {})["log_dir"] = os.getenv("FS_LOG_DIR")
        if os.getenv("FS_LOG_LEVEL"):
            self._raw.setdefault("logging", {})["level"] = os.getenv("FS_LOG_LEVEL")
        if os.getenv("FS_CONSOLE_LEVEL"):
            self._raw.setdefault("logging", {})["console_level"] = os.getenv("FS_CONSOLE_LEVEL")
    
    def _validate(self):
        """Validate and normalize configuration values."""
        pass
    
    @property
    def rpc_url(self) -> str:
        return self._raw.get("rpc", {}).get("url", "http://127.0.0.1:8332")
    
    @property
    def rpc_user(self) -> str:
        return self._raw.get("rpc", {}).get("user", "bitcoin")
    
    @property
    def rpc_password(self) -> str:
        return self._raw.get("rpc", {}).get("password", "")
    
    @property
    def poll_secs(self) -> int:
        return int(self._raw.get("polling", {}).get("poll_secs", 60))
    
    @property
    def rolling_window_mins(self) -> int:
        return int(self._raw.get("polling", {}).get("rolling_window_mins", 60))
    
    @property
    def alert_webhook_url(self) -> str:
        return self._raw.get("alerts", {}).get("webhook_url", "")
    
    @property
    def alert_min_change_secs(self) -> int:
        return int(self._raw.get("alerts", {}).get("min_change_secs", 300))
    
    @property
    def spike_detection_config(self) -> Dict[str, Any]:
        """Get spike detection configuration."""
        cfg = self._raw.get("spike_detection", {})
        return {
            "enabled": cfg.get("enabled", True),
            "spike_pct": int(cfg.get("spike_pct", 35)),
            "min_alert_satvb": int(cfg.get("min_alert_satvb", 15)),
            "cooldown_minutes": int(cfg.get("cooldown_minutes", 20)),
            "adjustment_rules": {
                "target_sat_vb_floor": int(cfg.get("adjustment_rules", {}).get("target_sat_vb_floor", 12)),
                "bump_pct_if_queue_backlog": int(cfg.get("adjustment_rules", {}).get("bump_pct_if_queue_backlog", 20)),
                "drop_pct_if_clearing_fast": int(cfg.get("adjustment_rules", {}).get("drop_pct_if_clearing_fast", 15))
            }
        }

    @property
    def consolidate_label(self) -> str:
        return self._raw.get("consolidation", {}).get("label", "feesentinel")
    
    @property
    def consolidate_min_utxo_sats(self) -> int:
        return int(self._raw.get("consolidation", {}).get("min_utxo_sats", 546))
    
    @property
    def consolidate_max_inputs(self) -> int:
        return int(self._raw.get("consolidation", {}).get("max_inputs", 50))
    
    @property
    def consolidate_target_address(self) -> str:
        return self._raw.get("consolidation", {}).get("target_address", "")
    
    @property
    def consolidate_min_trigger_satvb(self) -> int:
        return int(self._raw.get("consolidation", {}).get("min_trigger_satvb", 5))
    
    @property
    def psbt_cooldown_secs(self) -> int:
        return int(self._raw.get("consolidation", {}).get("psbt_cooldown_secs", 3600))
    
    @property
    def log_level(self) -> str:
        return self._raw.get("logging", {}).get("level", "INFO")
    
    @property
    def logfile(self) -> str:
        return self._raw.get("logging", {}).get("logfile", "")
    
    @property
    def log_dir(self) -> str:
        return self._raw.get("logging", {}).get("log_dir", "logs")
    
    @property
    def console_level(self) -> str:
        return self._raw.get("logging", {}).get("console_level", "INFO")
    
    @property
    def log_rotation(self) -> Dict[str, Any]:
        """Get log rotation configuration with defaults."""
        rotation = self._raw.get("logging", {}).get("rotation", {})
        return {
            "max_bytes": rotation.get("max_bytes", 10485760),  # 10MB
            "backup_count": rotation.get("backup_count", 30),
            "when": rotation.get("when", "midnight")
        }

    @property
    def structured_output_config(self) -> Dict[str, Any]:
        """Get structured output configuration with defaults.

        This controls JSONL files that can later be rolled into database tables.
        """
        cfg = self._raw.get("structured_output", {})
        base_dir = cfg.get("base_dir", str(Path(self.log_dir) / "structured"))
        return {
            "enabled": cfg.get("enabled", False),
            "base_dir": base_dir,
            "events_filename": cfg.get("events_filename", "events.jsonl"),
            "blocks_filename": cfg.get("blocks_filename", "blocks.jsonl"),
            "fee_alerts_filename": cfg.get("fee_alerts_filename", "fee_alerts.jsonl"),
            "fee_snapshots_filename": cfg.get("fee_snapshots_filename", "fee_snapshots.jsonl"),
        }

    @property
    def event_watcher_config(self) -> Dict[str, Any]:
        """Get event monitoring configuration with defaults."""
        event_config = self._raw.get("event_watcher", {})
        
        # Apply environment variable overrides
        if os.getenv("FS_EVENT_WATCHER_ENABLED"):
            event_config["enabled"] = os.getenv("FS_EVENT_WATCHER_ENABLED").lower() == "true"
        if os.getenv("FS_EVENT_POLL_INTERVAL"):
            event_config["poll_interval_secs"] = int(os.getenv("FS_EVENT_POLL_INTERVAL"))
        if os.getenv("FS_EVENT_WEBHOOK_URL"):
            event_config.setdefault("events", {})["webhook_url"] = os.getenv("FS_EVENT_WEBHOOK_URL")
        
        return {
            "enabled": event_config.get("enabled", False),
            "poll_interval_secs": event_config.get("poll_interval_secs", 10),
            "start_height": event_config.get("start_height"),
            "max_reorg_depth": event_config.get("max_reorg_depth", 6),
            "filters": {
                "treasury": {
                    "enabled": event_config.get("filters", {}).get("treasury", {}).get("enabled", False),
                    "addresses": event_config.get("filters", {}).get("treasury", {}).get("addresses", []),
                    "famous_addresses": event_config.get("filters", {}).get("treasury", {}).get("famous_addresses", []),
                    "clusters": event_config.get("filters", {}).get("treasury", {}).get("clusters", []),
                    "address_files": event_config.get("filters", {}).get("treasury", {}).get("address_files", []),
                    "watch_inputs": event_config.get("filters", {}).get("treasury", {}).get("watch_inputs", True),
                    "watch_outputs": event_config.get("filters", {}).get("treasury", {}).get("watch_outputs", True)
                },
                "ordinals": {
                    "enabled": event_config.get("filters", {}).get("ordinals", {}).get("enabled", False),
                    "detect_inscriptions": event_config.get("filters", {}).get("ordinals", {}).get("detect_inscriptions", True),
                    "hotspots": event_config.get("filters", {}).get("ordinals", {}).get("hotspots", [])
                },
                "covenants": {
                    "enabled": event_config.get("filters", {}).get("covenants", {}).get("enabled", False),
                    "patterns": event_config.get("filters", {}).get("covenants", {}).get("patterns", [])
                }
            },
            "events": {
                "webhook_url": event_config.get("events", {}).get("webhook_url", ""),
                "webhook_urls": event_config.get("events", {}).get("webhook_urls", []),
                "retry_attempts": event_config.get("events", {}).get("retry_attempts", 3),
                "retry_backoff_secs": event_config.get("events", {}).get("retry_backoff_secs", 5)
            },
            "state": {
                "backend": event_config.get("state", {}).get("backend", "sqlite"),
                "db_path": event_config.get("state", {}).get("db_path", "state/eventwatcher.db"),
                "json_path": event_config.get("state", {}).get("json_path", "state/eventwatcher.json")
            },
            "metrics": {
                "enabled": event_config.get("metrics", {}).get("enabled", True),
                "log_interval_secs": event_config.get("metrics", {}).get("log_interval_secs", 300)
            },
            # Convenience properties for state manager
            "state_backend": event_config.get("state", {}).get("backend", "sqlite"),
            "state_db_path": event_config.get("state", {}).get("db_path", "state/eventwatcher.db"),
            "state_json_path": event_config.get("state", {}).get("json_path", "state/eventwatcher.json")
        }

