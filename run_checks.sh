#!/usr/bin/env bash
# Runs every validation check. Exits non-zero if any fails.
set -e
cd "$(dirname "$0")"
python3 sanity.py | tail -1
python3 sanity_final.py | tail -1
python3 selfcheck_final.py | tail -2     # a few minutes
echo "all checks ran"
