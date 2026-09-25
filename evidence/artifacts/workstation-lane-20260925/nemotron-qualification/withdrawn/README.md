# Withdrawn: first recording of the workstation vLLM use receipt `-2`

`nativestack-5975wx-20260925--vllm--use--20260925-2.withdrawn.json` is the first
recording of the superseding vLLM use receipt for host
`nativestack-5975wx-20260925` (observed 2026-09-25T14:37:37Z, `catalog_revision`
`66fd7e96`). It was withdrawn from `evidence/hosts/` before merge. The file is
byte-for-byte what it was after its independent review: the recorder's self
`agree` and one `independent_session` `needs_changes`. It no longer counts
toward any status.

## Why it was withdrawn

It can never pass CI. Its `catalog_revision` names a local commit from before a
rebase. No GitHub ref reaches that commit, and the GitHub API returns 422 for it,
so `scripts/host_receipts.py validate` fails in CI. A receipt is never edited
after recording, so the fix is a new recording.

The reviewer's recorded reason (`reviews[1].ref`), verbatim:

> Adequacy-checked all four points and re-ran all nine commands on this host: points 1, 2 and 4 hold (/version 0.25.0 equals the foundation winner pin with pin_matches true, unit active with 0 restarts, backup passage ranked first, model_card_check.py v2 4/4 within 0.0011 of the card and v1 4/4 within 0.0009 of the laptop scores, rotated-documents control 0/4 with its ranking assertion failing, hf cache verify 15 files at c0c9fea93ea4 with the one-byte tamper control exiting 1, served model directory unchanged), but catalog_revision 66fd7e96 is the pre-rebase copy of this branch's SPY/LEAN replay commit and no origin ref reaches it, so the catalog revision behind the pin record cannot be resolved by a reader (point 3) and CI host_receipts.py validate fails on exactly this receipt (run 36149652903); re-record as -3 from a worktree at an origin/main revision.

The reviewer's non-blocking notes for the re-recording, verbatim from its session
report:

> - The rotated-control script exits 0 whenever the result is below 4/4, which is looser than the preregistered "must report 0/4". The observed 0/4 still meets the preregistered bar.
> - The claim and `bars` text say "within 0.005 of the card and the laptop scores". In fact v2 is compared only with the card and v1 only with the laptop run.
> - The preregistration was written about 3 minutes before recording. The receipt doesn't say whether the disclosed rehearsal ran before or after it.
> - Both receipts describe the host as "Ubuntu 24.04.5 / WSL 2.7.13" but keep no command for it. I reproduced both on this host.

## What replaced it

- `../model_card_check.py` `v1-rotated` now exits 0 only at exactly 0/4, as
  `../preregistration.txt` (Q4) requires.
- A new receipt was recorded at
  [`evidence/hosts/nativestack-5975wx-20260925/nativestack-5975wx-20260925--vllm--use--20260925-2.json`](../../../../hosts/nativestack-5975wx-20260925/nativestack-5975wx-20260925--vllm--use--20260925-2.json)
  (observed 2026-09-25T15:19:50Z, `catalog_revision` `8c7b7f3b`, which is on
  `main`). It was recorded from a detached worktree at `origin/main`, with
  `--supersedes nativestack-5975wx-20260925--vllm--use--20260925`. It adds an OS
  and WSL version command. Its claim names which run was compared with which
  baseline. Its limitations give the preregistration and rehearsal timing.
- The new receipt reuses the id `…-2`. Once this file left `evidence/hosts/`,
  `record` assigned the next free generation, and that is `-2` again. The two
  files are different recordings; tell them apart by path, `observed_at_utc` and
  `catalog_revision`. The new receipt needs its own `independent_session` review.
  The review in this file does not carry over.
