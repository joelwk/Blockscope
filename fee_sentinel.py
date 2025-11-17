#!/usr/bin/env python3
"""
Compatibility wrapper for fee_sentinel.py.
This script now delegates to the modular feesentinel package.
For new usage, prefer: python -m feesentinel
"""

from feesentinel.cli import main

if __name__ == "__main__":
    main()
