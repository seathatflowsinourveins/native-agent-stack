# Copy notes

The preregistration and the measurement's own files live in a private measurement folder in the workstation
distribution (`~/.local/state/native-agent-stack/new-wsl-measure-20261002/`). This folder publishes copies of 35 of
them. 33 are byte-identical copies; two carry one replacement each, listed below. `files.json` gives, for every
published copy, the original's path (relative to the measurement folder), size and sha256 and the copy's path, size and
sha256, and lists the other 196 files of the measurement folder by path, size and sha256.

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

## The other changed copy

`scripts/a2/a2_tasks.py` (original `a2/a2_tasks.py`, 4,198 bytes, sha256
`3900efc4a269ad0c790ed3bac6861f622e338290bf115bcb4d73054db81c1071`, the hash amendment 3b froze) is published as 4,211 bytes,
sha256 `49c5986d7c29414b…` (full value in `files.json`). Line 72 sets the git e-mail of the scratch repositories that the
client tasks commit in. The original value is the fixture address with local part `measure` at the reserved domain
`example.invalid` (RFC 2606); the copy writes `<fixture address at example.invalid>` there, so that no e-mail-shaped string
is published. To run the copy, put any address back; the tasks' file checks do not read it.

## Copies that are byte-identical

The two bootstrap outputs (`raw/M18-bootstrap.txt` as `part-a/bootstrap.txt`, `raw/PB-bootstrap.txt` as
`part-b/bootstrap.txt`), the four per-case validity files of the scored A2 runs, the per-query nDCG@10 files and summaries of
E1 to E3, the five A2 scorers and runners, the seven Part B scripts and nine step scripts. Their originals' hashes are the
ones the preregistration froze where it froze one (`a2_validity.py`, `a2_bootstrap.py`, `a2_run_bfcl.sh`, the corrected
`a2_run_client.sh` of deviation 2, the Part B scripts of amendment 4a, `steps/M14-a1-ext.py`, `steps/M23-partb-bootstrap.sh`,
and `steps/W-partb-window.sh` as changed in deviation 4 to `43254cf8…`).

Two hashes in the preregistration name a file's state at an earlier moment, as the preregistration says: `raw/_gpu-window.txt`
is the windows' append-only log (`b10e1388…` at deviation 1; later windows appended to it) and `steps/W-partb-window.sh` was
`688722f7…` at amendment 4a before deviation 4 changed it.

Every copy was made by a script that compared each replacement's count with the count above and stopped on any difference;
`scan_private.py` (the coordination lane's scanner: the repository's private-content patterns, the user name, home paths,
e-mail addresses, Windows names) reported no hit in the copies.
