## Blockscope

Bitcoin fee monitoring and blockchain event tracking with webhook alerts.

### What Blockscope does

- **Fee monitoring**: Tracks mempool fee percentiles, classifies them into human-readable buckets (free, normal, busy, peak, etc.), and sends webhook alerts when conditions change.
- **Spike detection**: Identifies sudden fee surges relative to trailing averages and suggests policy adjustments (e.g., raising fee floors during backlogs).
- **Event monitoring**: Watches the Bitcoin blockchain for activity you care about (treasury addresses, ordinals, covenants, etc.) and emits structured JSON events.
- **Service-friendly**: Designed to run continuously (systemd, Docker, cron) with clear logs and safe restart semantics.

### When you might use it

- **Scheduling transactions**: Get notified when fees drop into your preferred bucket before consolidating UTXOs or sending large transactions.
- **Watching treasuries**: Track famous or internal treasury addresses for deposits, withdrawals, or movements tied to specific entities.
- **Research / monitoring**: Follow ordinals activity, covenant flows, or other on-chain patterns without building your own indexer.

---

### Quick start

#### 1. Setup Python environment

```bash
./setup_venv.sh
# or manually
# python -m venv venv
# source venv/bin/activate  # On Windows: venv\Scripts\activate
# pip install -r requirements.txt
```

#### 2. Configure connection to your node

**Option A – Environment variables (recommended for production)**

```bash
export FS_RPC_URL="http://127.0.0.1:8332"
export FS_RPC_USER="bitcoin"
export FS_RPC_PASS="your_rpc_password"
# Optional: SSH tunnel target
export SSH_SERVER="user@hostname"
```

**Option B – Config file (simple for local dev)**

```bash
cp config.example.yaml config.yaml
# then edit config.yaml
```

See `config.example.yaml` for all available options.

#### 3. Run Blockscope

**Fee monitoring (mempool fees, alerts, optional PSBT prep)**

```bash
# Continuous monitoring (recommended)
./run_fee_sentinel.sh

# One-shot run (e.g., from cron)
./run_fee_sentinel.sh --once

# One-shot with PSBT preparation
./run_fee_sentinel.sh --prepare-psbt
```

**Event monitoring (blocks & transactions)**

```bash
# Continuous comprehensive monitoring (event + fee monitoring)
./run_event_watcher.sh

# One-shot comprehensive check (both event + fee monitoring)
./run_event_watcher.sh --once

# Only specific filter set (e.g., treasuries only)
./run_event_watcher.sh --event-mode treasury
```

**Note**: `run_event_watcher.sh` runs both event monitoring AND fee monitoring concurrently, providing comprehensive coverage. This ensures all structured output files (`events.jsonl`, `blocks.jsonl`, `fee_alerts.jsonl`, `fee_snapshots.jsonl`) are created.

You can also run directly via Python:

```bash
source venv/bin/activate
python -m feesentinel                 # Fee monitoring
python -m feesentinel --watch-events  # Event monitoring
```

---

### Basic configuration

All configuration values can be set via **environment variables** (`FS_*`) or **`config.yaml`**.

- **RPC**
  - `rpc.url` – Bitcoin RPC URL (default `http://127.0.0.1:8332`)
  - `rpc.user`, `rpc.password` – RPC credentials
- **Polling**
  - `polling.poll_secs` – Seconds between checks
  - `polling.rolling_window_mins` – Rolling window for fee statistics
- **Alerts (fee monitoring)**
  - `alerts.webhook_url` – Where fee bucket change alerts are sent
  - `alerts.min_change_secs` – Debounce between alerts of the same severity
- **Spike detection**
  - `spike_detection.enabled` – Enable/disable spike monitoring
  - `spike_detection.spike_pct` – % surge over trailing average to trigger alert (default 35%)
  - `spike_detection.cooldown_minutes` – Debounce between spike alerts
- **Consolidation (optional)**
  - `consolidation.target_address` – UTXO consolidation target address
  - `consolidation.min_utxo_sats`, `max_inputs`, `min_trigger_satvb`
- **Event monitoring**
  - `event_watcher.enabled` – Enable/disable monitoring
  - `event_watcher.filters` – Toggle `treasury`, `ordinals`, `covenants`
  - `event_watcher.events.webhook_url` – Where event JSON is sent
- **Structured output (JSONL logging)**
  - `structured_output.enabled` – Enable/disable JSONL file logging
  - `structured_output.base_dir` – Directory for JSONL files (default: `logs/structured`)
  - `structured_output.events_filename` – Filename for blockchain events
  - `structured_output.blocks_filename` – Filename for block summaries
  - `structured_output.fee_alerts_filename` – Filename for fee alerts (fee monitoring only)
  - `structured_output.fee_snapshots_filename` – Filename for fee snapshots (fee monitoring only)

For more detailed examples, see:

- `config.example.yaml` – full config surface
- `examples/treasuries.example.yaml` – example treasury registry

---

### CLI reference (minimal)

**Fee monitoring**

```bash
python -m feesentinel [OPTIONS]

Options:
  --config PATH       Path to config.yaml
  --dry-run           Send alerts only, no PSBT preparation
  --prepare-psbt      Prepare consolidation PSBT when fees are low
  --once              Run one iteration then exit
  --verbose           More logging in one-shot mode
```

**Event monitoring**

```bash
python -m feesentinel --watch-events [OPTIONS]

Options:
  --watch-events      Enable event monitoring mode
  --event-mode MODE   treasury | ordinals | covenants | all
  --once              Run one iteration then exit
  --config PATH       Path to config.yaml
```

---

### Webhooks & events (high level)

- **Fee alerts**: Sent when the current fee bucket changes (e.g., `normal → busy`).
- **Spike alerts**: Sent when fees jump significantly over the trailing average. Includes a "policy adjustment suggestion" (e.g., bump target floor).
- **Event payloads**: JSON describing the event type (treasury movement, ordinal inscription, covenant flow, block/reorg, etc.) plus basic metadata.
- **Retry logic**: Event webhooks are retried a configurable number of times on transient failures.

Inspect the `feesentinel/alerts.py`, `feesentinel/event_emitter.py`, and `feesentinel/event_runner.py` modules for the exact payload formats and retry logic.

---

### Structured output (JSONL logging)

When `structured_output.enabled` is `true` in your config, Blockscope writes all events and metrics to JSONL files in `logs/structured/` (or your configured `base_dir`). These files can be ingested into databases or analytical tools for historical analysis.

**Files created:**

- **`events.jsonl`**: All blockchain events (treasury movements, ordinal inscriptions, covenant flows, block confirmations, reorgs). One JSON object per line with `type`, `data`, `timestamp`, and optional `txid`/`block_height` fields.
- **`blocks.jsonl`**: Per-block summaries with transaction counts, events emitted, and cumulative metrics. Written after each block is processed.
- **`fee_alerts.jsonl`**: Fee bucket change alerts and PSBT preparation events. Only created when fee monitoring runs.
- **`fee_snapshots.jsonl`**: Periodic fee snapshots with rolling statistics. Written on each fee monitoring iteration. Only created when fee monitoring runs.

**Event types in `events.jsonl`:**

- `treasury_utxo_spent` / `treasury_utxo_received` / `treasury_utxo_both` – Treasury address activity
- `ordinal_inscription` – Ordinal inscription detected
- `covenant_flow` – Covenant pattern detected (e.g., OP_CHECKTEMPLATEVERIFY)
- `block_confirmed` – New block confirmed
- `reorg_detected` – Chain reorganization detected

**Configuration:**

```yaml
structured_output:
  enabled: true  # Enable JSONL logging
  base_dir: "logs/structured"
  events_filename: "events.jsonl"
  blocks_filename: "blocks.jsonl"
  fee_alerts_filename: "fee_alerts.jsonl"
  fee_snapshots_filename: "fee_snapshots.jsonl"
```

**When files are created:**

- `events.jsonl` and `blocks.jsonl`: Created when event monitoring runs (`--watch-events` or `run_event_watcher.sh`)
- `fee_alerts.jsonl` and `fee_snapshots.jsonl`: Created when fee monitoring runs (`python -m feesentinel` or `run_event_watcher.sh`)

**Note**: When using `run_event_watcher.sh` (or `python -m feesentinel --watch-events`), both event monitoring and fee monitoring run concurrently, so all 4 files are created. If you run fee monitoring separately (`python -m feesentinel` without `--watch-events`), only the fee monitoring files are created.

---

### Running in production

- **systemd**: See `examples/fee-sentinel.service` for a ready-to-adapt service unit.
- **cron**: Run `./run_fee_sentinel.sh --once` or `python -m feesentinel --once` on a schedule.
- **SSH tunnels**: Use `start_tunnel_bg.sh` / `stop_tunnel.sh` if your node is behind SSH.

---

### Project layout

```text
.
├── config.example.yaml      # Example configuration
├── config.yaml              # Local configuration (gitignored)
├── feesentinel/             # Python package
│   ├── runner.py            # Fee monitoring loop
│   ├── event_runner.py      # Event monitoring loop
│   ├── block_monitor.py     # Block fetch & reorg handling
│   ├── transaction_filter.py # Filter logic (treasuries, ordinals, covenants)
│   ├── treasury_registry.py # Registry of notable addresses/entities
│   ├── alerts.py            # Fee alerts
│   ├── event_emitter.py     # Event webhooks
│   ├── state_manager.py     # Idempotency & persistence
│   └── ...                  # Other helpers (config, fees, buckets, logging, etc.)
├── run_fee_sentinel.sh      # Fee monitoring launcher
├── run_event_watcher.sh     # Event monitoring launcher
├── examples/                # systemd + treasury examples
├── scripts/                 # Helper scripts
└── tests/                   # Unit tests
```

---

### Contributing, security, and license

- **Contributing**: See `CONTRIBUTING.md` for development guidelines, code style, and test expectations.
- **Security**: See `SECURITY.md` for guidance on running Blockscope safely and handling credentials.
- **License**: MIT – see `LICENSE`.

