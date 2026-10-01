#!/usr/bin/env bash
# Canary proof omniroute-lane consumer (window step W8): one read-only GPT-6 run through the packaged loopback gateway
# lane, with the lane home registered at prepare, and no capture file.
#
#   bash tools/credentials/canary_lane_consumer.sh RUN ATTEMPT LANE_HOME </dev/null >/dev/null 2>&1
#
# Modelled on the durable lane launcher run_gpt6_gateway_review.sh (profile stack-worker, model cx/gpt-6-astra at
# effort max, read-only sandbox, skip-git-repo-check), minus its review.md and codex.log captures: client stdin,
# stdout and stderr are /dev/null and there is no -o/--output-last-message. The loopback gateway is keyless: the
# placeholder assignment below is the literal the packaged runner uses, held in this file so that the operator's
# command never names the variable. The session rollout stays in LANE_HOME (sink A4), where the proof looks for it.
set -u
run=${1:-} attempt=${2:-} lane_home=${3:-}
if [[ ! "$run" =~ ^cp-[0-9]{8}t[0-9]{6}z-[0-9a-f]{6}$ || ! "$attempt" =~ ^[1-9][0-9]*$ || "$lane_home" != /* || ! -d "$lane_home" ]]; then
    printf 'canary_lane_consumer: usage: RUN ATTEMPT LANE_HOME (an absolute, registered lane home)\n' >&2
    exit 2
fi
cd "$(dirname "$0")/../.." || exit 2
prompt="Run exactly this command once with your shell tool from the repository root, then reply done. Run nothing else.
python3 -I tools/credentials/credential_run.py canary-e2e -- python3 -I tools/credentials/canary_probe.py --run $run --consumer omniroute-lane --attempt $attempt"
CODEX_HOME="$lane_home" OMNIROUTE_API_KEY=local-loopback timeout 900 codex exec -p stack-worker --skip-git-repo-check \
    -s read-only -m cx/gpt-6-astra -c 'model_reasoning_effort="max"' "$prompt" </dev/null >/dev/null 2>&1
status=$?
printf 'canary_lane_consumer: codex exit %s\n' "$status" >&2
exit "$status"
