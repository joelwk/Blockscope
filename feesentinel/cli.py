"""Command-line interface for Blockscope."""

import sys
import json
import argparse
from .config import Config
from .runner import FeeSentinelRunner
from .event_runner import EventWatcherRunner
from .logging import setup_logging, get_logger

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

    # Check if event monitoring mode is enabled
    if args.watch_events or config.event_watcher_config.get("enabled"):
        # Event monitoring mode
        event_config = config.event_watcher_config
        
        # Override filter settings based on --event-mode
        if args.event_mode != "all":
            event_config["filters"]["treasury"]["enabled"] = (args.event_mode == "treasury")
            event_config["filters"]["ordinals"]["enabled"] = (args.event_mode == "ordinals")
            event_config["filters"]["covenants"]["enabled"] = (args.event_mode == "covenants")
        
        runner = EventWatcherRunner(config)
        
        if args.once:
            # One-shot event watching
            try:
                result = runner.run_once()
                output = {
                    "processed": result["processed"],
                    "height": result["height"],
                    "metrics": result["metrics"]
                }
                if result.get("block_hash"):
                    output["block_hash"] = result["block_hash"]
                if result.get("reorg"):
                    output["reorg"] = result["reorg"]
                
                if args.verbose:
                    print(json.dumps(output, indent=2))
                else:
                    print(json.dumps(output))
                logger.debug(f"One-shot event watching completed: {json.dumps(output)}")
            except Exception as e:
                logger.error(f"Error in one-shot event watching: {e}", exc_info=True)
                print(f"Error: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            # Continuous event watching
            poll_interval = event_config.get("poll_interval_secs", 10)
            runner.run_continuous(poll_interval)
        
        return

    # Fee monitoring mode (default)
    runner = FeeSentinelRunner(config)

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

