#!/bin/bash
# Quick setup script for Bitcoin project virtual environment

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install required packages
pip install --upgrade pip
pip install requests pyyaml

# Verify installation
pip list

echo "Virtual environment ready! Activate with: source venv/bin/activate"

