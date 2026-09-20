# Native container storage on macOS

Apple container 1.4.1 and the official PostgreSQL 18.6 image passed a small
database persistence check on the Mac coordinator. A native ext4 volume retained
an inserted row across `container stop` and `container start`. No host port was
published. The [receipt](receipt.json) and [native recovery output](recovery-checks.json)
retain the exact image digest, runtime identity, exits, timing and limits.

The original Documents-directory bind mount blocked in
`VZSharedDirectory -> open`; the empty source directory remained untouched.
Native service restart alone did not fix that mount. After clearing the stalled
runtime, the same image without a bind started in 0.67 seconds, and a native
volume started in 0.51 seconds. The macOS cause remains unknown. No privacy
permissions, security attributes or unrelated services were changed. This is a
qualified storage alternative, not proof that arbitrary bind mounts work.

Use the [upstream volume and container commands](https://github.com/apple/container/blob/1.4.1/docs/command-reference.md)
in a deliberately selected fixture scope. The names below must be unused; never
delete an existing resource to make them available. The image remains pinned to
the reviewed multi-platform digest; this receipt executed its Linux arm64 variant.

```sh
container --version
container volume create --label scope=native-agent-stack-container-recovery \
  -s 256M ledger-volume-probe-20260920
container run --detach --name ledger-volume-db-20260920 \
  --label scope=native-agent-stack-container-recovery --cpus 1 --memory 512M \
  --volume ledger-volume-probe-20260920:/var/lib/postgresql \
  --env POSTGRES_HOST_AUTH_METHOD=trust --env POSTGRES_DB=ledger \
  docker.io/library/postgres@sha256:86c951e05bf56c93d95d397747fb8820ac76cc3bedb78f43abd83eedbe3666ae
container exec ledger-volume-db-20260920 pg_isready -U postgres -d ledger
```

Wait for readiness to return zero before issuing SQL. This trust-authenticated
fixture has no published host port and contains no private or production data.
It does not configure production authentication, network policy or durability.

```sh
container exec ledger-volume-db-20260920 psql -U postgres -d ledger \
  -v ON_ERROR_STOP=1 -At -c "CREATE TABLE recovery_probe (id integer PRIMARY KEY, value text NOT NULL); INSERT INTO recovery_probe VALUES (1, 'native-volume-retained'); SELECT value FROM recovery_probe WHERE id=1;"
container stop --time 5 ledger-volume-db-20260920
container start ledger-volume-db-20260920
container exec ledger-volume-db-20260920 pg_isready -U postgres -d ledger
container exec ledger-volume-db-20260920 psql -U postgres -d ledger \
  -v ON_ERROR_STOP=1 -At -c 'SELECT value FROM recovery_probe WHERE id=1;'
```

Readiness must pass after restart too. The final value must be
`native-volume-retained`. Every native command above returned zero in the
recorded trial. After preserving the evidence, remove only the owned fixture:

```sh
container stop --time 5 ledger-volume-db-20260920
container delete ledger-volume-db-20260920
container volume delete ledger-volume-probe-20260920
```

Cleanup passed; the coordinator's container list was empty afterward. No model
calls ran. This small local check does not establish crash/reboot recovery,
whole-host disaster recovery, workload performance or token savings.
