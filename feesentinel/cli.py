"""Command-line interface for Blockscope."""

import sys
import json
import argparse
import threading
import time
from .config import Config
from .runner import FeeSentinelRunner
from .event_runner import EventWatcherRunner
from .logging import setup_logging, get_logger
from .structured_output import StructuredOutputWriter

logger = get_logger(__name__)


def main():
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Monitor mempool fees and alert on bucket changes; "
                    "optionally prepare consolidation PSBTs."
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to config.yaml (default: search for config.yaml)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="No side effects beyond alerts"
    )
    parser.add_argument(
        "--prepare-psbt",
        action="store_true",
        help="Prepare consolidation PSBT when fees <= trigger"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one iteration then exit (cron-friendly)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose output (for --once mode)"
    )
    parser.add_argument(
        "--watch-events",
        action="store_true",
        help="Enable event monitoring mode (monitor blocks/transactions)"
    )
    parser.add_argument(
        "--event-mode",
        choices=["treasury", "ordinals", "covenants", "all"],
        default="all",
        help="Event filter mode (default: all)"
    )

    args = parser.parse_args()
    
    try:
        config = Config(args.config)
    except FileNotFoundError as e:
        # Initialize basic logging before setup_logging for error reporting
        import logging
        logging.basicConfig(level=logging.ERROR, format='[%(levelname)s] %(message)s')
        logger.error(f"Config file not found: {e}")
        sys.exit(1)
    except Exception as e:
        import logging
        logging.basicConfig(level=logging.ERROR, format='[%(levelname)s] %(message)s')
        logger.error(f"Error loading config: {e}")
        sys.exit(1)
    
    # Initialize logging system after config is loaded
    setup_logging(config)
    logger = get_logger(__name__)

    # Optional structured output writer for JSONL records
    structured_writer = None
    structured_cfg = config.structured_output_config
    if structured_cfg.get("enabled"):
        structured_writer = StructuredOutputWriter(
            base_dir=structured_cfg["base_dir"],
            events_filename=structured_cfg["events_filename"],
            blocks_filename=structured_cfg["blocks_filename"],
            fee_alerts_filename=structured_cfg["fee_alerts_filename"],
            fee_snapshots_filename=structured_cfg["fee_snapshots_filename"],
        )

    # Check if event monitoring mode is enabled
    if args.watch_events or config.event_watcher_config.get("enabled"):
        # Event monitoring mode (can run alongside fee monitoring)
        event_config = config.event_watcher_config

        # Override filter settings based on --event-mode
        if args.event_mode != "all":
            event_config["filters"]["treasury"]["enabled"] = (args.event_mode == "treasury")                                                                    
            event_config["filters"]["ordinals"]["enabled"] = (args.event_mode == "ordinals")                                                                    
            event_config["filters"]["covenants"]["enabled"] = (args.event_mode == "covenants")                                                                  

        event_runner = EventWatcherRunner(config, structured_writer=structured_writer)
        
        # Also run fee monitoring alongside event monitoring for comprehensive coverage
        fee_runner = FeeSentinelRunner(config, structured_writer=structured_writer)

        if args.once:
            # One-shot mode: run both once
            try:
                # Run event monitoring
                event_result = event_runner.run_once()
                # Run fee monitoring
                fee_result = fee_runner.run_once(args.prepare_psbt)
                
                output = {
                    "event_monitoring": {
                        "processed": event_result["processed"],
                        "height": event_result["height"],
                        "metrics": event_result["metrics"]
                    },
                    "fee_monitoring": {
                        "snapshot": fee_result["snapshot"],
                        "rolling_stats": fee_result["rolling_stats"],
                        "bucket": fee_result["bucket"],
                        "timestamp": fee_result["timestamp"]
                    }
                }
                if event_result.get("block_hash"):
                    output["event_monitoring"]["block_hash"] = event_result["block_hash"]
                if event_result.get("reorg"):
                    output["event_monitoring"]["reorg"] = event_result["reorg"]
                if "psbt" in fee_result:
                    output["fee_monitoring"]["psbt"] = fee_result["psbt"]

                if args.verbose:
                    print(json.dumps(output, indent=2))
                else:
                    print(json.dumps(output))
                logger.debug(f"One-shot comprehensive run completed: {json.dumps(output)}")                                                                        
            except Exception as e:
                logger.error(f"Error in one-shot comprehensive run: {e}", exc_info=True)                                                                           
                print(f"Error: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            # Continuous mode: run both in parallel threads
            logger.info("Starting comprehensive monitoring: event monitoring + fee monitoring")
            
            def run_event_monitoring():
                """Run event monitoring in a separate thread."""
                try:
                    poll_interval = event_config.get("poll_interval_secs", 10)
                    event_runner.run_continuous(poll_interval)
                except Exception as e:
                    logger.error(f"Event monitoring thread error: {e}", exc_info=True)
                    sys.exit(1)
            
            def run_fee_monitoring():
                """Run fee monitoring in a separate thread."""
                try:
                    fee_runner.run_continuous(config.poll_secs, args.dry_run, args.prepare_psbt)
                except Exception as e:
                    logger.error(f"Fee monitoring thread error: {e}", exc_info=True)
                    sys.exit(1)
            
            # Start both threads
            event_thread = threading.Thread(target=run_event_monitoring, daemon=True)
            fee_thread = threading.Thread(target=run_fee_monitoring, daemon=True)
            
            event_thread.start()
            fee_thread.start()
            
            # Wait for both threads (they run indefinitely)
            try:
                event_thread.join()
                fee_thread.join()
            except KeyboardInterrupt:
                logger.info("Shutting down comprehensive monitoring...")
                sys.exit(0)

        return

    # Fee monitoring mode only (default when --watch-events not specified)
    runner = FeeSentinelRunner(config, structured_writer=structured_writer)

    if args.once:
        # One-shot mode for cron
        try:
            result = runner.run_once(args.prepare_psbt)
            output = {
                "snapshot": result["snapshot"],
                "rolling_stats": result["rolling_stats"],
                "bucket": result["bucket"],
                "timestamp": result["timestamp"]
            }
            if "psbt" in result:
                output["psbt"] = result["psbt"]
            
            if args.verbose:
                print(json.dumps(output, indent=2))
            else:
                print(json.dumps(output))
            logger.debug(f"One-shot run completed: {json.dumps(output)}")
        except Exception as e:
            logger.error(f"Error in one-shot run: {e}", exc_info=True)
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Continuous mode
        runner.run_continuous(config.poll_secs, args.dry_run, args.prepare_psbt)


if __name__ == "__main__":
    main()

