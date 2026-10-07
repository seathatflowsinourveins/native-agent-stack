#!/bin/sh
# Local adaptation (v2) for OmniRoute release/v3.8.51, used only on the omniroute.service PATH (recorded 2026-09-30; v1 is the 2026-09-27 shim).
# What it works around: `omniroute serve` refuses to start when its port preflight finds a process on the port. The preflight
# (bin/cli/utils/pid.mjs findListeningPids, called by bin/cli/commands/serve.mjs resolveServeBusyPids) runs `lsof -ti :PORT`, which lists every process
# with a socket on the port, CLIENTS included. A client that keeps a pooled connection open (a CLOSE-WAIT socket once the server is gone) therefore makes
# a restart, or systemd's automatic restart after a crash, fail with "Port is already in use" although nothing listens; v1 did not change that.
# Reference implementation: upstream's own fallback for an unusable discovery tool. resolveServeBusyPids (#14518) turns a null result into a bind probe
# of the port, which still refuses a real second listener. This shim answers the one query the preflight makes (`lsof -ti :PORT`) with exit status 2 and
# no output, which findListeningPids reports as null (only exit 1 with empty output means "no match"), so the bind probe is the guard.
# Every other lsof call passes through unchanged. It also covers what v1 covered: the no-match status 1 no longer reaches the caller.
case "$*" in
  "-ti :"*) exit 2 ;;
esac
exec /usr/bin/lsof "$@"
