## Blockscope

Bitcoin fee monitoring and blockchain event tracking with webhook alerts.

### What Blockscope does

- **Fee monitoring**: Tracks mempool fee percentiles, classifies them into human-readable buckets (free, normal, busy, peak, etc.), and sends webhook alerts when conditions change.
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
# Continuous event monitoring
./run_event_watcher.sh

# One-shot event check
./run_event_watcher.sh --once

# Only specific filter set (e.g., treasuries only)
./run_event_watcher.sh --event-mode treasury
```

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
- **Consolidation (optional)**
  - `consolidation.target_address` – UTXO consolidation target address
  - `consolidation.min_utxo_sats`, `max_inputs`, `min_trigger_satvb`
- **Event monitoring**
  - `event_watcher.enabled` – Enable/disable monitoring
  - `event_watcher.filters` – Toggle `treasury`, `ordinals`, `covenants`
  - `event_watcher.events.webhook_url` – Where event JSON is sent

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
- **Event payloads**: JSON describing the event type (treasury movement, ordinal inscription, covenant flow, block/reorg, etc.) plus basic metadata.
- **Retry logic**: Event webhooks are retried a configurable number of times on transient failures.

Inspect the `feesentinel/alerts.py`, `feesentinel/event_emitter.py`, and `feesentinel/event_runner.py` modules for the exact payload formats and retry logic.

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

