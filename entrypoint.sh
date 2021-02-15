#!/bin/sh

set -e

export PYTHONPATH="${PYTHONPATH}:/app"

if [[ -z "${RTPE_OPERATOR}" ]]; then
    python3 app.py --config_file config/sample-config.conf
else
    python3 rtpe_operator/op.py
fi

exec "$@"