"""Constants used throughout the Blockscope application."""

# Bitcoin unit conversions
SATOSHIS_PER_BTC = 100_000_000  # 1e8
VB_PER_KB = 1000  # Virtual bytes per kilobyte
WEIGHT_TO_VSIZE_RATIO = 4.0  # Weight units to virtual size conversion

# Fee rate conversions
SATVB_TO_BTCKVB_FACTOR = 1e-5  # sat/vB to BTC/kvB conversion factor

# Default configuration values
DEFAULT_POLL_SECS = 60
DEFAULT_ROLLING_WINDOW_MINS = 60
DEFAULT_ALERT_MIN_CHANGE_SECS = 300
DEFAULT_MIN_UTXO_SATS = 546  # Bitcoin dust threshold
DEFAULT_MAX_INPUTS = 50
DEFAULT_MIN_TRIGGER_SATVB = 5
DEFAULT_PSBT_COOLDOWN_SECS = 3600  # 1 hour
DEFAULT_POLL_INTERVAL_SECS = 10
DEFAULT_RETRY_BACKOFF_SECS = 5
DEFAULT_METRICS_LOG_INTERVAL_SECS = 300  # 5 minutes

# Log rotation defaults
DEFAULT_LOG_MAX_BYTES = 10_485_760  # 10MB
DEFAULT_LOG_BACKUP_COUNT = 30

# Network timeouts
DEFAULT_HTTP_TIMEOUT_SECS = 10
DEFAULT_CONNECTION_RETRY_DELAY_SECS = 10

# Bitcoin RPC defaults
MAX_CONFIRMATIONS = 9_999_999  # Effectively unconfirmed + all confirmed

# Fee bucket limits
EXTREME_BUCKET_MAX_SATVB = 10_000  # Practical cap for extreme bucket

# Percentile calculation
PERCENTILE_SCALE = 100.0  # Percentile scale (0-100)

