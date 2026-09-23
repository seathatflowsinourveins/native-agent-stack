# $1 = outside dir, $2 = decoy file. Each probe prints its exit code; success would show as EXIT:0 / rc=0.
curl -sS -m 8 -o /dev/null -w "PROBE egress HTTPSTATUS:%{http_code} EXIT:%{exitcode}\n" https://example.com; echo "PROBE egress curl_rc=$?"
( echo x > "$1/probe-write.txt" ) 2>&1; echo "PROBE write_outside rc=$?"
cat "$2" 2>&1; echo "PROBE read_decoy rc=$?"
