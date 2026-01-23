#!/usr/bin/env bash
# exit on error
set -o errexit

# Upgrade pip
pip install --upgrade pip

# Install packages with no cache to reduce memory
pip install --no-cache-dir -r requirements.txt