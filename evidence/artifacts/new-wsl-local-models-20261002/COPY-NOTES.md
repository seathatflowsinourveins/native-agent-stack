# Copy notes

The preregistration and the measurement's own files live in a private measurement folder in the workstation
distribution (`~/.local/state/native-agent-stack/new-wsl-measure-20261002/`). This folder publishes copies of 35 of
them. 32 are byte-identical copies; three carry one replacement each, listed below. `files.json` gives, for every
published copy, the original's path (relative to the measurement folder), size and sha256 and the copy's path, size and
sha256, and lists the other 196 files the folder held when it was listed by path, size and sha256. A copy-out of the
throwaway distribution's measurement directories was added to the folder after that listing; `files.json` lists it by
its own checksum list (`added_after_listing`).

## The preregistration

| | Path | Bytes | sha256 |
| --- | --- | ---: | --- |
| Original | `PREREGISTRATION-local-models.md` in the measurement folder | 66,331 | `d161feaacd6b3082b3adf37e80a368b58bd6f68205efd399102b8d84d0d0f78b` |
| Copy | `PREREGISTRATION-local-models.md` here | 66,312 | `454f879d03d61fa5a8e9f0d877e62cd94878abcd32f8f09b16ac9514492c3a0b` |

The original's sha256 is the last entry of its hash chain (`PREREGISTRATION-local-models.sha256`, copied unchanged:
2,988 bytes, sha256 `7645e3a1bd9d94c478849ae20b07dc3f6b6f7a778ec0dfe74715b6123b71021a`, 16 entries from
2026-10-02T15:31:48Z to 2026-10-03T00:03:17Z). The chain hashes the original, not this copy.

Replacements, by the classes the publication rule names, counted in the original before copying:

| What | Occurrences | Written as |
| --- | ---: | --- |
| A home path | 0 | (none to replace; `~` where a path would appear) |
| The throwaway distribution's name | 1 | line 12: the words "the throwaway distribution" followed by the name in backticks became "the throwaway distribution", so the words are not doubled |
| The destination distribution's name | 0 | (none) |
| The user name | 0 | (none) |
| Windows names (the computer name, a Windows user path) | 0 | (none) |

Nothing else differs: the copy is the original with that one span shortened by 19 bytes. The original's name for the
throwaway distribution is in the private record, so the coordinator can reverse the replacement and recompute
`d161feaa…`.

## The other changed copies

`scripts/a2/a2_tasks.py` (original `a2/a2_tasks.py`, 4,198 bytes, sha256
`3900efc4a269ad0c790ed3bac6861f622e338290bf115bcb4d73054db81c1071`, the hash amendment 3b froze) is published as 4,211 bytes,
sha256 `49c5986d7c29414b…` (full value in `files.json`). Line 72 sets the git e-mail of the scratch repositories that the
client tasks commit in. The original value is the fixture address with local part `measure` at the reserved domain
`example.invalid` (RFC 2606); the copy writes `<fixture address at example.invalid>` there, so that no e-mail-shaped string
is published. To run the copy, put any address back; the tasks' file checks do not read it.

`scripts/steps/W-partb-window.sh` (original `steps/W-partb-window.sh`, 5,769 bytes, sha256
`43254cf88c50540c6725148b03fcdc25e5373938a70516910775b0e9041783e2`, the file as deviation 4 changed it) is published as
5,783 bytes, sha256 `7f0e285d79c8bcaf812db7eb06e3f5ac05067e7038c9ffe53d38a5ffb8fd0fa2`. Line 18 named the throwaway
distribution as the argument of `wsl.exe -d`; the copy writes `'<the throwaway distribution>'` there, quoted so that the
copy still parses with `bash -n`. Nothing else differs. The name is in the private record, so the replacement can be
reversed and `43254cf8…` recomputed.

## Copies that are byte-identical

The preregistration's hash chain, the two bootstrap outputs (`raw/M18-bootstrap.txt` as `part-a/bootstrap.txt`,
`raw/PB-bootstrap.txt` as `part-b/bootstrap.txt`), the four per-case validity files of the scored A2 runs, the per-query
nDCG@10 files and summaries of E1 to E3, four A2 scorers and runners (`a2_validity.py`, `a2_bootstrap.py`,
`a2_run_bfcl.sh`, `a2_run_client.sh`), the seven Part B scripts and eight of the nine step scripts (all but
`W-partb-window.sh`). Their originals' hashes are the ones the preregistration froze where it froze one (`a2_validity.py`,
`a2_bootstrap.py`, `a2_run_bfcl.sh`, the corrected `a2_run_client.sh` of deviation 2, the Part B scripts of amendment 4a,
`steps/M14-a1-ext.py` and `steps/M23-partb-bootstrap.sh`).

Two hashes in the preregistration name a file's state at an earlier moment, as the preregistration says: `raw/_gpu-window.txt`
is the windows' append-only log (`b10e1388…` at deviation 1; later windows appended to it) and `steps/W-partb-window.sh` was
`688722f7…` at amendment 4a before deviation 4 changed it.

## Checks of the copies

Every copy was made by a script that compared each replacement's count with the count above and stopped on any difference.
The first publication missed one class: `scripts/steps/W-partb-window.sh` was published unchanged with the throwaway
distribution's name in it, because `scan_private.py` (the coordination lane's scanner: the repository's private-content
patterns, the user name, home paths, e-mail addresses, the Windows computer name) has no pattern for distribution names.
The repair of 2026-10-03 replaced it as above and scanned every file of this folder, case-insensitively, for the name of
every WSL distribution registered on the workstation and for the Windows computer name. One match remains: line 10 of
`W-partb-window.sh` names the workstation's generation service unit, whose name contains the workstation distribution's
name and which the repository already published before this change. Neither the throwaway's nor the destination's name
occurs, and `scan_private.py` reports no hit in the copies.
