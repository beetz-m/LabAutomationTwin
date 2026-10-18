#!/usr/bin/env bash
# Run a list of Isaac Sim regressions sequentially (one GPU slot), one log each, and print the pass lines.
# Usage: tools/run_regressions.sh <tag> "<script args>" ["<script args>" ...]
#   e.g. tools/run_regressions.sh fitout "scripts/test_r03.py" "scripts/test_h4_robot.py --scene cell01 --place-mode drop"
# The GPU budget is two concurrent simulations: run at most two of these at once (never next to path tracing).
set -uo pipefail
cd "$(dirname "$0")/.."
tag=$1
shift
for job in "$@"; do
    name=$(echo "$job" | sed -E 's#scripts/##; s#\.py##; s#--#_#g; s# +#_#g; s#_+#_#g')
    log="regress_${tag}_${name}.log"
    echo "=== $job -> $log"
    OMNI_KIT_ACCEPT_EULA=YES env_isaacsim/bin/python -u $job > "$log" 2>&1
    echo "exit=$? $(grep -E '[0-9]+/[0-9]+ passed|-> (PASS|FAIL)|(PASS|FAIL)$' "$log" | tail -2 | tr '\n' ' ')"
done
