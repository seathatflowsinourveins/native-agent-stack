#!/usr/bin/env bash
# Local integration: openai/codex rust-v0.162.0 scripts/install/install.sh:947-969.
# Native gh 2.102.0, tar, sha256sum, and the existing Codex identity wrapper.
# Canary launching remains a co-op-owned executable, not an authored task runner.
set -euo pipefail
umask 077
phase=${1:?condition, stage, canary, promote or rollback}
: "${CURRENCY_STATE:?}" "${CURRENCY_RELEASES:?}" "${CURRENCY_LAUNCHER:?}"
: "${CURRENCY_PROTECTED:?}" "${CURRENCY_RECORD:?}" "${CURRENCY_CANARY:?}"
case "$CURRENCY_STATE:$CURRENCY_RELEASES:$CURRENCY_LAUNCHER:$CURRENCY_PROTECTED:$CURRENCY_RECORD:$CURRENCY_CANARY" in
  *$'\n'*) echo 'Paths must not contain newlines' >&2; exit 2 ;;
esac
CURRENCY_ROOT="$CURRENCY_STATE"
if test "$phase" != condition; then
  : "${CURRENCY_RUN:?Native Dagu run id, or an explicit fixture run id}"
  case "$CURRENCY_RUN" in *[!a-zA-Z0-9_.-]*|'') echo 'Invalid run id' >&2; exit 2 ;; esac
  CURRENCY_STATE="$CURRENCY_STATE/runs/$CURRENCY_RUN"
fi
mkdir -p "$CURRENCY_STATE"
record() {
  printf '## CODEX-CURRENCY %s utc=%s phase=%s source=%s install_docs=%s\n' "$1" "$(date -u +%FT%TZ)" "$phase" \
    "https://github.com/openai/codex/releases/tag/${tag:-rust-v0.162.0}" \
    'https://developers.openai.com/codex/cli' >> "$CURRENCY_RECORD"
}
network() {
  local rc=0
  timeout 300 "$@" || rc=$?
  if test "$rc" -ne 0; then
    printf '## OMNI-ERROR codex-currency-upstream-command rc=%s utc=%s phase=%s\n' "$rc" "$(date -u +%FT%TZ)" "$phase" >> "$CURRENCY_RECORD"
  fi
  return "$rc"
}
guard() {
  if test -e "$CURRENCY_PROTECTED" || test -L "$CURRENCY_PROTECTED"; then
    record 'REFUSED protected-window-present'
    return 75
  fi
}
previous_path() {
  # Contract of observability/collector/codex-identity-launcher.sh.example.
  tail -n 1 "$CURRENCY_LAUNCHER" | sed -n "s/^exec '\([^']*\)' \"\\\$@\"$/\1/p"
}
load_transaction() {
  tag=$(jq -er '.tag' "$CURRENCY_STATE/transaction.json")
  version=$(jq -er '.version' "$CURRENCY_STATE/transaction.json")
  previous=$(jq -er '.previous' "$CURRENCY_STATE/transaction.json")
  candidate=$(jq -er '.candidate' "$CURRENCY_STATE/transaction.json")
  download="$CURRENCY_ROOT/stages/$version"
}
package_state() {
  # Bounded by the checked publisher archive, not a filesystem/home-tree walk.
  while IFS= read -r member; do
    case "$member" in /*|..|../*|*/../*) echo 'Unsupported archive member' >&2; return 2 ;; esac
    file="${candidate%/bin/codex}/$member"
    printf '%s\t' "$member"
    LC_ALL=C stat -c '%a:%F' -- "$file"
    if test -L "$file"; then readlink -- "$file";
    elif test -f "$file"; then sha256sum "$file" | cut -d ' ' -f 1; fi
  done < "$download/archive-members.txt"
}
verify_package() {
  package_state > "$download/package-now.native"
  test "$(sha256sum "$download/package-now.native" | cut -d ' ' -f 1)" = "$(jq -er '.package_sha256' "$CURRENCY_STATE/transaction.json")"
}
verify_evidence() {
  canonical_root=$(realpath -e "$CURRENCY_STATE")
  jq -r '.lanes[].evidence[] | [.sha256,.path] | @tsv' "$CURRENCY_STATE/canary.json" |
    while IFS=$'\t' read -r digest path; do
      resolved=$(realpath -e "$path")
      case "$resolved" in "$canonical_root"/*) ;; *) echo 'Evidence outside owned state' >&2; exit 2 ;; esac
      test -f "$resolved"
      printf '%s  %s\n' "$digest" "$resolved" | sha256sum --check
    done
}
case "$phase" in
condition)
  # systemd ExecCondition 1-254 skips activation without marking the unit failed.
  guard || exit 1
  ;;
stage)
  guard
  test -x "$CURRENCY_CANARY"
  previous=$(previous_path)
  test -f "$CURRENCY_LAUNCHER"
  test ! -L "$CURRENCY_LAUNCHER"
  test -n "$previous"
  test -x "$previous"
  case "$previous" in "$CURRENCY_RELEASES"/*/bin/codex) ;; *) echo 'Unrecognized previous distribution' >&2; exit 2 ;; esac
  network gh api repos/openai/codex/releases/latest > "$CURRENCY_STATE/release.json"
  tag=$(jq -er 'select(.draft == false and .prerelease == false) | .tag_name | select(test("^rust-v[0-9]+\\.[0-9]+\\.[0-9]+$"))' "$CURRENCY_STATE/release.json")
  version=${tag#rust-v}
  previous_version=$("$previous" --version)
  if test "$previous_version" = "codex-cli $version"; then
    rm -f "$CURRENCY_STATE/transaction.json"
    record 'CURRENT'
    exit 0
  fi
  # Follow the vendor stable-alias policy; never move a newer default backward.
  test "$(printf '%s\n%s\n' "${previous_version#codex-cli }" "$version" | sort -V | tail -n 1)" = "$version"
  test "$(uname -m)" = x86_64
  test "$(uname -s)" = Linux
  asset=codex-package-x86_64-unknown-linux-musl.tar.gz
  candidate="$CURRENCY_RELEASES/$version-x86_64-unknown-linux-musl/bin/codex"
  download="$CURRENCY_ROOT/stages/$version"
  mkdir -p "$download"
  digest=$(jq -er --arg asset "$asset" '.assets[] | select(.name == $asset) | .digest | select(test("^sha256:[a-f0-9]{64}$")) | sub("^sha256:";"")' "$CURRENCY_STATE/release.json")
  if test -e "${candidate%/bin/codex}"; then
    # Reuse only a stage bound to this archive digest. Foreign/prior manual stages refuse.
    test -f "$download/stage-binary.sha256"
    test -f "$download/stage-archive.sha256"
    test "$(cut -d ' ' -f 1 "$download/stage-archive.sha256")" = "$digest"
    sha256sum --check "$download/stage-binary.sha256"
    sha256sum --check "$download/stage-archive.sha256"
    package_state > "$download/package-reuse.native"
    cmp "$download/package-state.native" "$download/package-reuse.native"
  else
    # No overwrite: retain failed attempts for review rather than clobber their bytes.
    attempt="$CURRENCY_STATE/download"
    mkdir "$attempt"
    network gh release download "$tag" --repo openai/codex --pattern "$asset" --pattern codex-package_SHA256SUMS --dir "$attempt"
    # Only complete downloads enter the reusable shared provenance directory.
    cp "$attempt/$asset" "$attempt/codex-package_SHA256SUMS" "$download/"
    checksum_rc=0
    (
      cd "$download"
      printf '%s  %s\n' "$digest" "$asset" | sha256sum --check
      awk -v asset="$asset" '$2 == asset || $2 == "*" asset' codex-package_SHA256SUMS > selected.sha256
      test "$(wc -l < selected.sha256)" -eq 1
      sha256sum --check selected.sha256
    ) > "$CURRENCY_STATE/checksum-native.txt" 2>&1 || checksum_rc=$?
    test "$checksum_rc" -eq 0 || exit "$checksum_rc"
    cp "$CURRENCY_STATE/checksum-native.txt" "$download/checksum-native.txt"
    tar -tzf "$download/$asset" > "$download/archive-members.txt"
    scratch=$(mktemp -d "$CURRENCY_RELEASES/.currency-$version.XXXXXXXX")
    tar -xzf "$download/$asset" -C "$scratch"
    test -x "$scratch/bin/codex"
    test -x "$scratch/bin/codex-code-mode-host"
    test -x "$scratch/codex-path/rg"
    guard
    mv "$scratch" "${candidate%/bin/codex}"
    sha256sum "$candidate" > "$download/stage-binary.sha256"
    sha256sum "$download/$asset" > "$download/stage-archive.sha256"
    package_state > "$download/package-state.native"
  fi
  test "$("$candidate" --version)" = "codex-cli $version"
  cp "$CURRENCY_LAUNCHER" "$CURRENCY_STATE/launcher-before"
  chmod --reference="$CURRENCY_LAUNCHER" "$CURRENCY_STATE/launcher-before"
  jq -n --arg tag "$tag" --arg version "$version" --arg previous "$previous" \
    --arg previous_version "${previous_version#codex-cli }" --arg candidate "$candidate" \
    --arg binary_sha256 "$(sha256sum "$candidate" | cut -d ' ' -f 1)" \
    --arg package_sha256 "$(sha256sum "$download/package-state.native" | cut -d ' ' -f 1)" \
    --arg launcher_sha256 "$(sha256sum "$CURRENCY_LAUNCHER" | cut -d ' ' -f 1)" \
    '{tag:$tag,version:$version,previous:$previous,previous_version:$previous_version,candidate:$candidate,binary_sha256:$binary_sha256,package_sha256:$package_sha256,launcher_sha256:$launcher_sha256}' > "$CURRENCY_STATE/transaction.json.tmp"
  mv "$CURRENCY_STATE/transaction.json.tmp" "$CURRENCY_STATE/transaction.json"
  jq -r '.body' "$CURRENCY_STATE/release.json" > "$download/release-notes.md"
  rm -f "$CURRENCY_STATE/canary.json" "$CURRENCY_STATE/canary-validation.txt" "$CURRENCY_STATE/canary-evidence-native.txt" "$CURRENCY_STATE/canary-approved.json" "$CURRENCY_STATE/promotion.json"
  record "STAGED version=$version checksum=published-package-manifest canary=pending"
  ;;
canary)
  test -f "$CURRENCY_STATE/transaction.json" || exit 0
  load_transaction
  guard
  rm -f "$CURRENCY_STATE/canary-approved.json"
  verify_package
  # hcom b2a7c192 launcher.rs:1188-1226 resolves caller PATH before child-env rebuilding.
  # The co-op adapter dispatches exactly two parked lanes and their existing queued tasks.
  PATH="${candidate%/codex}:$PATH" timeout 1200 "$CURRENCY_CANARY" "$candidate" "$previous" "$CURRENCY_STATE/canary.json" "$download/release-notes.md"
  jq -e --arg version "$version" --arg previous "$(jq -r '.previous_version' "$CURRENCY_STATE/transaction.json")" \
    --arg executable "$candidate" --arg binary_hash "$(jq -r '.binary_sha256' "$CURRENCY_STATE/transaction.json")" \
    --arg tag "$tag" --arg notes_hash "$(sha256sum "$download/release-notes.md" | cut -d ' ' -f 1)" \
    'def count: type == "number" and . >= 0 and floor == .;
     def counts: (.tool_counts | type == "object") and
       all(.tool_counts[]; count) and ([.tool_counts[]] | add) == .tool_calls;
     def accounted(category; total):
       ([.error_dispositions[]? | select(.category == category) | .count] | add // 0) == total;
     .evidence_class == "native_proven" and .version == $version and .previous_version == $previous and
     .release_review.tag == $tag and .release_review.source == ("https://github.com/openai/codex/releases/tag/" + $tag) and
     .release_review.install_documentation == "https://developers.openai.com/codex/cli" and
     .release_review.notes_sha256 == $notes_hash and .release_review.approved_for_canary == true and
     (.release_review.reviewer | type == "string" and length > 0) and
     (.release_review.declared_breaking_items | type == "array") and all(.release_review.declared_breaking_items[]; type == "string") and
     (.release_review.compatibility_items | type == "array") and all(.release_review.compatibility_items[]; type == "string") and
     (.lanes | length == 2) and ([.lanes[].lane] | unique | length == 2) and
     all(.lanes[];
       (.lane | type == "string" and length > 0 and . != "paper-open-e2e") and .was_parked == true and
       .selected_executable == $executable and .current.binary_sha256 == $binary_hash and
       .baseline.version == $previous and .current.version == $version and
       (.baseline.turn | type == "string" and length > 0) and (.current.turn | type == "string" and length > 0) and
       (.queued_task | type == "string" and length > 0) and .queued_task_complete == true and
       (.thread | type == "string" and length > 0) and
       (.tools_smoke | length == 7) and ([.tools_smoke[].tool] | unique | length == 7) and
       all(.tools_smoke[]; .ok == true and (.tool | type == "string" and length > 0)) and
       (.baseline.tool_calls | count) and (.current.tool_calls | count and . > 0) and
       ((.baseline | counts) or (.baseline.tool_calls == 0 and .baseline.tool_counts == {})) and (.current | counts) and
       all([.baseline.native_errors,.baseline.mcp_errors,.baseline.provider_errors,.baseline.retries,
            .current.native_errors,.current.mcp_errors,.current.provider_errors,.current.retries][]; count) and
       .current.provider_errors == 0 and
       accounted("native"; .current.native_errors) and accounted("mcp"; .current.mcp_errors) and
       all(.error_dispositions[]?;
         (.category == "native" or .category == "mcp") and (.count | count and . > 0) and
         .candidate_caused == false and (.explanation | type == "string" and length > 0) and
         (.source | type == "string" and startswith("https://")) and
         (.failure_text_sha256 | test("^[a-f0-9]{64}$"))) and
       (.evidence | length > 0) and
       all(.evidence[]; (.path | type == "string" and length > 0) and (.sha256 | test("^[a-f0-9]{64}$"))))' \
    "$CURRENCY_STATE/canary.json" > "$CURRENCY_STATE/canary-validation.txt"
  # Only sanitized native metadata in this run's state, never raw conversations/auth.
  verify_evidence > "$CURRENCY_STATE/canary-evidence-native.txt" 2>&1
  jq -n --arg receipt "$(sha256sum "$CURRENCY_STATE/canary.json" | cut -d ' ' -f 1)" \
    --arg transaction "$(sha256sum "$CURRENCY_STATE/transaction.json" | cut -d ' ' -f 1)" \
    '{receipt_sha256:$receipt,transaction_sha256:$transaction}' > "$CURRENCY_STATE/canary-approved.json"
  record "CANARY-PASS version=$version lanes=2 tools_smoke=7/7-each"
  ;;
promote)
  test -f "$CURRENCY_STATE/transaction.json" || exit 0
  load_transaction
  guard
  test -s "$CURRENCY_STATE/canary-validation.txt"
  grep -qx true "$CURRENCY_STATE/canary-validation.txt"
  test -s "$CURRENCY_STATE/canary-evidence-native.txt"
  test "$(sha256sum "$CURRENCY_STATE/canary.json" | cut -d ' ' -f 1)" = "$(jq -er '.receipt_sha256' "$CURRENCY_STATE/canary-approved.json")"
  test "$(sha256sum "$CURRENCY_STATE/transaction.json" | cut -d ' ' -f 1)" = "$(jq -er '.transaction_sha256' "$CURRENCY_STATE/canary-approved.json")"
  verify_evidence > "$CURRENCY_STATE/canary-evidence-promote-native.txt" 2>&1
  verify_package
  test "$(sha256sum "$download/release-notes.md" | cut -d ' ' -f 1)" = "$(jq -er '.release_review.notes_sha256' "$CURRENCY_STATE/canary.json")"
  test "$(sha256sum "$candidate" | cut -d ' ' -f 1)" = "$(jq -r '.binary_sha256' "$CURRENCY_STATE/transaction.json")"
  test "$(sha256sum "$CURRENCY_LAUNCHER" | cut -d ' ' -f 1)" = "$(jq -r '.launcher_sha256' "$CURRENCY_STATE/transaction.json")"
  # Same substitution route as the identity wrapper's documented native sed installation.
  case "$candidate$previous" in *[!a-zA-Z0-9_./-]*) echo 'Unsupported path alphabet' >&2; exit 2 ;; esac
  rendered=$(mktemp "$CURRENCY_LAUNCHER.currency.XXXXXXXX")
  backup="$CURRENCY_STATE/launcher-before"
  test "$(sha256sum "$backup" | cut -d ' ' -f 1)" = "$(jq -r '.launcher_sha256' "$CURRENCY_STATE/transaction.json")"
  pattern=${previous//./\\.}
  sed "s#$pattern#$candidate#g" "$backup" > "$rendered"
  bash -n "$rendered"
  chmod --reference="$CURRENCY_LAUNCHER" "$rendered"
  guard
  test -f "$CURRENCY_LAUNCHER"
  test ! -L "$CURRENCY_LAUNCHER"
  test "$(sha256sum "$CURRENCY_LAUNCHER" | cut -d ' ' -f 1)" = "$(jq -r '.launcher_sha256' "$CURRENCY_STATE/transaction.json")"
  jq -n --arg before "$(sha256sum "$CURRENCY_LAUNCHER" | cut -d ' ' -f 1)" \
    --arg after "$(sha256sum "$rendered" | cut -d ' ' -f 1)" '{before:$before,after:$after}' > "$CURRENCY_STATE/promotion.json"
  mv "$rendered" "$CURRENCY_LAUNCHER"
  record "PASS selected=$version pickup=next-launch"
  ;;
rollback)
  if test ! -f "$CURRENCY_STATE/transaction.json"; then record 'FAIL rollback=no-selection-change'; exit 0; fi
  load_transaction
  current_hash=$(sha256sum "$CURRENCY_LAUNCHER" | cut -d ' ' -f 1)
  test -f "$CURRENCY_LAUNCHER"
  test ! -L "$CURRENCY_LAUNCHER"
  if test "$current_hash" = "$(jq -r '.launcher_sha256' "$CURRENCY_STATE/transaction.json")"; then
    record "FAIL rollback=previous-retained previous=$previous"
  elif test -f "$CURRENCY_STATE/promotion.json" && test "$current_hash" = "$(jq -r '.after' "$CURRENCY_STATE/promotion.json")"; then
    backup="$CURRENCY_STATE/launcher-before"
    test "$(sha256sum "$backup" | cut -d ' ' -f 1)" = "$(jq -r '.launcher_sha256' "$CURRENCY_STATE/transaction.json")"
    restored=$(mktemp "$CURRENCY_LAUNCHER.rollback.XXXXXXXX")
    cp "$backup" "$restored"
    chmod --reference="$backup" "$restored"
    guard
    test "$(sha256sum "$CURRENCY_LAUNCHER" | cut -d ' ' -f 1)" = "$current_hash"
    mv "$restored" "$CURRENCY_LAUNCHER"
    record "FAIL rollback=restored previous=$previous"
  else
    record 'FAIL rollback=refused-foreign-launcher-change'
    exit 2
  fi
  ;;
*) echo 'Unknown phase' >&2; exit 2 ;;
esac
