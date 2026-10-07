#!/bin/bash
nativestack doctor
result=$?
printf '\nDoctor exit: %s. Commands: nativestack doctor | nativestack upstream | nativestack chat\n' "$result"
printf 'Reports are local health/freshness evidence. No automatic upgrade or service repair runs here.\n\n'
exec /bin/bash -l
