#!/bin/sh
# Repeat the committed oracle module N times (default 30) and print one line per run: a generated pipe whose right side never reads can kill its
# writer with SIGPIPE, so a run of real bash is not deterministic in principle; this shows whether the committed seeds are stable.
#   sh repeat-oracle.sh [N]        (from the repository root, with the parser and bash installed)
n=${1:-30}
i=1
failed=0
while [ "$i" -le "$n" ]; do
  if python3 -B -m unittest tests.test_command_position_oracle > /dev/null 2>&1; then echo "run $i ok"; else echo "run $i FAILED"; failed=$((failed + 1)); fi
  i=$((i + 1))
done
echo "$failed of $n runs failed"
[ "$failed" -eq 0 ]
