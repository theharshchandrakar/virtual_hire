#!/usr/bin/env bash
set -euo pipefail

# Applies pending Alembic migrations before the process starts. A no-op
# today (alembic/versions/ is empty, target_metadata is None per
# alembic/env.py) but keeps container startup self-contained once E1's
# migrations land. Only one process type should run this until E14 adds
# per-worker task definitions - see docker-compose.yml.
alembic upgrade head

exec "$@"
