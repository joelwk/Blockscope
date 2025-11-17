# Blockscope

A modular, configurable Bitcoin fee monitoring and event monitoring tool.

## Fee Monitoring

Blockscope's fee monitoring module polls your Bitcoin node, computes rolling fee percentiles from the mempool, and triggers webhooks/alerts when fee buckets change. Uses empirically-grounded fee buckets (free, cheap, normal, busy, high, peak, extreme) instead of arbitrary numeric thresholds. Supports dry-run mode and optional PSBT preparation for UTXO consolidation.

## Event Monitoring

Blockscope's event monitoring service listens to the Bitcoin node (or indexer) for new transactions/blocks, filters what you care about (e.g., UTXOs touching treasury addresses, ordinals, covenant flows), and emits reliable events to your systems. Designed to be idempotent, reorg-safe, and observable.

## Features

### Fee Monitoring
- **Mempool Fee Monitoring**: Computes p25, p50, p75, p90, p95 percentiles from live mempool data
- **Rolling Window Statistics**: Tracks fee trends over a configurable time window
- **Fee Bucket Classification**: Maps fees into named buckets (zero, free, cheap, normal, busy, high, peak, extreme) based on empirical market data
- **Bucket Change Alerts**: Webhook notifications when fee buckets change (by severity)
- **UTXO Consolidation**: Optional PSBT preparation for consolidating small UTXOs when fees are low

### Event Monitoring
- **Treasury Address Monitoring**: Watch for UTXO activity on famous addresses (genesis, hacks, seizures, burns)
- **Ordinal Detection**: Detect ordinal inscriptions in transactions
- **Covenant Detection**: Identify covenant flow patterns
- **Idempotent & Reorg-Safe**: No duplicate events, handles chain reorganizations gracefully
- **Multiple Webhooks**: Support for multiple event endpoints with retry logic

### General
- **Service-Friendly**: Designed to run as a long-running service or via cron
- **SSH Tunnel Integration**: Seamless integration with SSH tunnel management scripts

## Quick Start

### 1. Setup Virtual Environment

```bash
./setup_venv.sh
```

This creates a `venv` directory and installs required dependencies (`requests`, `pyyaml`).

### 2. Configure

**Option 1: Environment Variables (Recommended for Production)**

Set environment variables (no files to manage):

```bash
export FS_RPC_USER="bitcoin"
export FS_RPC_PASS="your_rpc_password"
export FS_RPC_URL="http://127.0.0.1:8332"
export SSH_SERVER="user@hostname"  # If using SSH tunnel
```

**Option 2: Config File (For Local Development)**

1. Copy the example config:
   ```bash
   cp config.example.yaml config.yaml
   ```

2. Edit `config.yaml` with your credentials (this file is gitignored):
   ```yaml
   rpc:
     url: "http://127.0.0.1:8332"
     user: "bitcoin"
     password: "your_rpc_password"
   ```

**Configuration Precedence** (highest to lowest):
1. Environment variables (`FS_*` prefix)
2. `config.yaml` (gitignored - safe for local secrets)
3. Default values

**Note:** Treasury addresses in `config.yaml` are public Bitcoin addresses and safe to commit. Only RPC credentials and webhook URLs should be kept private.

See `config.example.yaml` for all available configuration options.

### 3. Run

**Fee Monitoring:**
```bash
# Continuous monitoring (recommended)
./run_fee_sentinel.sh

# One-shot mode (for cron)
./run_fee_sentinel.sh --once

# With PSBT preparation
./run_fee_sentinel.sh --prepare-psbt
```

**Event Monitoring (Block/Transaction Monitoring):**
```bash
# Continuous event monitoring
./run_event_watcher.sh

# One-shot event check
./run_event_watcher.sh --once

# Watch specific filters only
./run_event_watcher.sh --event-mode treasury
```

**Manual Execution:**
```bash
source venv/bin/activate
python -m feesentinel                    # Fee monitoring
python -m feesentinel --watch-events     # Event monitoring
```

The launcher scripts automatically handle virtual environment activation, SSH tunnel management, and cleanup.

## Configuration

The `config.yaml` file supports the following sections:

### RPC Settings
- `rpc.url`: Bitcoin RPC URL (default: `http://127.0.0.1:8332`)
- `rpc.user`: RPC username (default: `bitcoin`)
- `rpc.password`: RPC password

### Polling Settings
- `polling.poll_secs`: Seconds between polls (default: `60`)
- `polling.rolling_window_mins`: Rolling window size in minutes (default: `60`)

### Alert Settings
- `alerts.webhook_url`: Webhook URL for alerts (empty to disable)
- `alerts.min_change_secs`: Minimum seconds between alerts for same bucket severity (default: `300`)

### Fee Buckets

Blockscope uses empirically-grounded fee buckets based on p50 sat/vB:

| Bucket Name | Label                            | Range (p50 sat/vB) | Severity |
|-------------|----------------------------------|-------------------|----------|
| `zero`      | No reliable fee data             | 0                 | 0        |
| `free`      | Free blocks / near-empty mempool | 1                 | 1        |
| `cheap`     | Very low fees                    | 2-5               | 2        |
| `normal`    | Normal fee market                | 6-15              | 3        |
| `busy`      | Busy but reasonable              | 16-40             | 4        |
| `high`      | High congestion                  | 41-100            | 5        |
| `peak`      | Peak mania                       | 101-250           | 6        |
| `extreme`   | Extreme blockspace stress        | >250              | 7        |

Alerts are triggered when the fee bucket changes (by severity), not on arbitrary numeric thresholds.

### Consolidation Settings
- `consolidation.target_address`: Target address for UTXO consolidation (empty to disable)
- `consolidation.min_utxo_sats`: Minimum UTXO size to include (default: `546`)
- `consolidation.max_inputs`: Maximum inputs per PSBT (default: `50`)
- `consolidation.min_trigger_satvb`: Fee threshold to trigger consolidation (default: `5`)

### Environment Variable Overrides

Any config value can be overridden using environment variables with the `FS_` prefix:

- `FS_RPC_URL` → `rpc.url`
- `FS_RPC_USER` → `rpc.user`
- `FS_RPC_PASS` → `rpc.password`
- `FS_POLL_SECS` → `polling.poll_secs`
- `FS_ROLLING_WINDOW_MINS` → `polling.rolling_window_mins`
- `FS_ALERT_WEBHOOK` → `alerts.webhook_url`
- `FS_ALERT_MIN_CHANGE_SECS` → `alerts.min_change_secs`
- `FS_CONSOLIDATE_TARGET_ADDR` → `consolidation.target_address`
- `FS_CONSOLIDATE_MIN_UTXO_SATS` → `consolidation.min_utxo_sats`
- `FS_CONSOLIDATE_MAX_INPUTS` → `consolidation.max_inputs`
- `FS_CONSOLIDATE_MIN_TRIGGER_SATVB` → `consolidation.min_trigger_satvb`

## CLI Usage

### Fee Monitoring Mode

```bash
python -m feesentinel [OPTIONS]

Options:
  --config PATH       Path to config.yaml (default: search for config.yaml)
  --dry-run          No side effects beyond alerts
  --prepare-psbt     Prepare consolidation PSBT when fees <= trigger
  --once             Run one iteration then exit (cron-friendly)
  --verbose          Verbose output (for --once mode)
```

**Examples:**

```bash
# Continuous monitoring with alerts
python -m feesentinel

# Dry-run mode (alerts only, no PSBTs)
python -m feesentinel --dry-run

# One-shot mode for cron
python -m feesentinel --once

# With PSBT preparation
python -m feesentinel --prepare-psbt
```

### Event Monitoring Mode

```bash
python -m feesentinel --watch-events [OPTIONS]

Options:
  --watch-events     Enable event monitoring mode
  --event-mode MODE  Filter mode: treasury, ordinals, covenants, or all (default: all)
  --once             Run one iteration then exit (cron-friendly)
  --config PATH      Path to config.yaml
```

**Examples:**

```bash
# Continuous event monitoring (all filters)
python -m feesentinel --watch-events

# Watch only treasury addresses
python -m feesentinel --watch-events --event-mode treasury

# Watch only ordinals
python -m feesentinel --watch-events --event-mode ordinals

# One-shot event check
python -m feesentinel --watch-events --once
```

### Using Launcher Scripts

**Fee Monitoring:**
```bash
# Default mode
./run_fee_sentinel.sh

# With options
./run_fee_sentinel.sh --once --prepare-psbt
```

**Event Monitoring:**
```bash
# Continuous mode
./run_event_watcher.sh

# With options
./run_event_watcher.sh --event-mode treasury --once
```

The launcher scripts automatically handle:
- Virtual environment activation
- SSH tunnel startup and verification
- Cleanup on exit (Ctrl+C)

## SSH Tunnel Management

The project includes scripts for managing SSH tunnels to remote Bitcoin nodes:

- `start_tunnel.sh`: Start tunnel in foreground (keeps terminal open)
- `start_tunnel_bg.sh`: Start tunnel in background (stores PID in `.tunnel.pid`)
- `stop_tunnel.sh`: Stop tunnel using PID file or port detection

**Configuration:** Set the `SSH_SERVER` or `FS_SSH_SERVER` environment variable:
```bash
export SSH_SERVER="user@hostname"
```

The `run_fee_sentinel.sh` launcher automatically manages the tunnel lifecycle.

## Running as a Service

### systemd Example

Create `/etc/systemd/system/fee-sentinel.service`:

```ini
[Unit]
Description=Blockscope - Bitcoin Fee Monitoring & Event Watching
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/bitcoin
ExecStart=/path/to/bitcoin/run_fee_sentinel.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable fee-sentinel
sudo systemctl start fee-sentinel
```

### Cron Example

For periodic one-shot runs:

```cron
# Run every 5 minutes
*/5 * * * * cd /path/to/bitcoin && ./start_tunnel_bg.sh && source venv/bin/activate && python -m feesentinel --once && ./stop_tunnel.sh
```

Or if tunnel is managed separately:

```cron
*/5 * * * * cd /path/to/bitcoin && source venv/bin/activate && python -m feesentinel --once
```

## Webhook Payload Format

### Fee Bucket Change Alert

```json
{
  "type": "fee_bucket_change",
  "bucket": {
    "name": "normal",
    "label": "Normal fee market",
    "severity": 3,
    "range_satvb": [6, 15]
  },
  "observed": {
    "p50": 10,
    "p75": 12,
    "p95": 15,
    "rolling_avg": 9,
    "tx": 4306
  },
  "ts": "2024-01-01T12:00:00Z"
}
```

The alert fires when the fee bucket changes (by severity). The `bucket` object contains:
- `name`: Short bucket identifier (e.g., "normal", "busy", "peak")
- `label`: Human-readable description
- `severity`: Monotone severity level (0-7) for deduplication and dashboards
- `range_satvb`: [min, max] sat/vB range for this bucket

### PSBT Preparation

```json
{
  "type": "psbt_prepare",
  "result": {
    "status": "ok",
    "inputs": 15,
    "psbt_path": "/path/to/consolidate_1234567890_5satvb.psbt",
    "target_satvb": 5
  },
  "ts": "2024-01-01T12:00:00Z"
}
```

## Project Structure

```
.
├── config.example.yaml      # Example configuration (safe to commit)
├── config.yaml              # Your configuration (gitignored)
├── feesentinel/             # Python package
│   ├── config.py            # Configuration loading
│   ├── rpc.py               # Bitcoin RPC client
│   ├── fees.py              # Fee percentile calculations
│   ├── buckets.py           # Fee bucket classification
│   ├── rolling.py           # Rolling window statistics
│   ├── alerts.py            # Alert management
│   ├── consolidation.py     # PSBT preparation
│   ├── runner.py            # Fee monitoring main loop
│   ├── event_runner.py      # Event monitoring main loop
│   ├── block_monitor.py     # Block monitoring
│   ├── transaction_filter.py # Transaction filtering
│   ├── treasury_registry.py # Treasury address registry
│   ├── event_emitter.py     # Event emission
│   ├── state_manager.py    # State persistence
│   └── cli.py              # Command-line interface
├── run_fee_sentinel.sh     # Blockscope fee monitoring launcher
├── run_event_watcher.sh    # Blockscope event monitoring launcher
├── start_tunnel_bg.sh      # SSH tunnel management
├── stop_tunnel.sh          # Stop SSH tunnel
├── setup_venv.sh           # Virtual environment setup
└── tests/                  # Unit tests
```

## Testing

Run tests with pytest:

```bash
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install pytest
pytest tests/ -v
```

## Event Monitoring Details

Blockscope's event monitoring module monitors Bitcoin blocks and transactions, filters for specific patterns, and emits reliable events to external systems.

### Configuration

Enable event monitoring in `config.yaml`:

```yaml
event_watcher:
  enabled: true
  poll_interval_secs: 10
  filters:
    treasury:
      enabled: true
      # Let the internal registry own the core big addresses (USG, hacks, monuments)
      addresses: []   # Use this ONLY for additional custom ones you care about
      famous_addresses:
        - id: "genesis_satoshi"
          label: "Genesis / Satoshi"
          category: "protocol_monument"
          addresses:
            - "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
      clusters:
        - id: "usg_treasury"
          label: "US Government Bitcoin Holdings"
          category: "USG_seizure"
          addresses:
            - "bc1qa5wkgaew2dkv56kfvj49j0av5nml45x9ek9hz6"
    ordinals:
      enabled: true
      detect_inscriptions: true  # Keep enabled; relies on heuristics
    covenants:
      enabled: false  # Start disabled; re-enable when you have specific patterns to watch
    # (Future) hotspots:
    #   enabled: true
    #   addresses:
    #     - "..."  # Specific experiment or ordinals marketplace addresses
  events:
    webhook_url: "https://your-webhook-url.com/events"
    retry_attempts: 3
```

See `config.example.yaml` for complete configuration options and `examples/treasuries.example.yaml` for treasury address examples.

### Event Types

- `treasury_utxo_spent` - UTXO spent from watched address
- `treasury_utxo_received` - UTXO received to watched address
- `treasury_utxo_both` - Both spend and receive
- `ordinal_inscription` - Ordinal inscription detected
- `covenant_flow` - Covenant pattern detected
- `block_confirmed` - New block confirmed
- `reorg_detected` - Chain reorganization detected

### Event Payload Example

```json
{
  "type": "treasury_utxo_spent",
  "txid": "abc123...",
  "block_height": 850000,
  "timestamp": "2024-01-01T12:00:00Z",
  "data": {
    "addresses": ["bc1qa5wkgaew2dkv56kfvj49j0av5nml45x9ek9hz6"],
    "enriched_addresses": [
      {
        "address": "bc1qa5wkgaew2dkv56kfvj49j0av5nml45x9ek9hz6",
        "category": "USG_seizure",
        "entity_id": "silk_road_individual_x",
        "entity_label": "Silk Road 'Individual X' Seizure (USG)"
      }
    ],
    "entities": [
      {
        "id": "silk_road_individual_x",
        "label": "Silk Road 'Individual X' Seizure (USG)",
        "category": "USG_seizure"
      }
    ]
  }
}
```

## Architecture

### Fee Monitoring Components

- **`feesentinel/fees.py`**: Mempool fee percentile calculations
- **`feesentinel/buckets.py`**: Fee bucket classification and policies
- **`feesentinel/rolling.py`**: Rolling window statistics
- **`feesentinel/alerts.py`**: Webhook alert management
- **`feesentinel/consolidation.py`**: UTXO consolidation PSBT preparation
- **`feesentinel/runner.py`**: Main monitoring loop
- **`feesentinel/config.py`**: Configuration loading with environment variable support
- **`feesentinel/constants.py`**: Application-wide constants

### Event Monitoring Components

- **`feesentinel/event_runner.py`**: Main event monitoring loop
- **`feesentinel/block_monitor.py`**: Block monitoring and reorg handling
- **`feesentinel/transaction_filter.py`**: Transaction filtering logic
- **`feesentinel/treasury_registry.py`**: Treasury address registry with metadata
- **`feesentinel/event_emitter.py`**: Event emission with retry logic
- **`feesentinel/state_manager.py`**: State persistence (SQLite/JSON) for idempotency

## Troubleshooting

### Connection Issues

- **RPC connection failed**: Ensure your Bitcoin node is running and RPC is enabled
- **SSH tunnel errors**: Verify `SSH_SERVER` environment variable is set correctly
- **Authentication errors**: Check that RPC credentials are set via environment variables or in `config.yaml`

### Logging

Logs are written to the `logs/` directory by default. Check:
- `logs/feesentinel.log` - Main application log
- `logs/feesentinel-error.log` - Error log

Adjust log levels in `config.yaml`:
```yaml
logging:
  level: "DEBUG"  # For verbose output
  console_level: "INFO"  # Console output level
```

### Common Issues

- **No fee data**: Ensure mempool has transactions, or check RPC connection
- **PSBT creation fails**: Verify wallet is loaded and has sufficient UTXOs
- **Webhook not firing**: Check webhook URL is correct and network is accessible
- **Event monitoring not detecting events**: Verify filters are enabled in config and addresses are correct
- **Connection errors**: Ensure SSH tunnel is running and RPC credentials are correct

## Security

**Important Security Notes:**

- Never commit `config.yaml` with real credentials (it's gitignored)
- Use environment variables for production (recommended) or put secrets in `config.yaml` for local development
- Rotate credentials if they've been exposed in git history
- See [SECURITY.md](SECURITY.md) for detailed security guidelines

## Disclaimer

**This software is provided "as is" without warranty of any kind.**

- Blockscope is for monitoring Bitcoin fees and events and does not constitute financial advice
- Users are responsible for their own Bitcoin transactions and UTXO management
- Always review PSBTs before signing and broadcasting
- The authors are not responsible for any loss of funds or other damages
- Use at your own risk

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) file for details.

