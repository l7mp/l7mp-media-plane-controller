#!/bin/sh

set -e

export PYTHONPATH="${PYTHONPATH}:/app"

if [[ -z "${RTPE_CONTROLLER}" ]]; then
    python3 rtpeController/app.py --config_file config/sample-config.conf
else
    python3 -u rtpeController/controller.py
fi

exec "$@"