#!/usr/bin/env bash
set -euo pipefail
profile_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
: "${MERLIN_EXPECTED_SOURCE_SHA:?exact checked-out source SHA is required}"
: "${MERLIN_PARALLAX_ARTIFACTS:?new bounded artifact directory is required}"
exec python3 -B "$profile_dir/ci_driver.py" \
  --expected-sha "$MERLIN_EXPECTED_SOURCE_SHA" \
  --artifacts "$MERLIN_PARALLAX_ARTIFACTS"
