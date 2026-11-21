#!/bin/bash
# Launch EPS Visibility. Pass --sim to start in simulation mode (no hardware).
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="/tmp/venv"
if [ ! -f "$VENV/bin/python" ]; then
    echo "Creating virtual environment in $VENV..."
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install -r "$DIR/requirements.txt"
fi
export MPLCONFIGDIR=/tmp/matplotlib
export DISPLAY="${DISPLAY:-:0}"
cd "$DIR"
exec "$VENV/bin/python" -m eps_visibility "$@"
