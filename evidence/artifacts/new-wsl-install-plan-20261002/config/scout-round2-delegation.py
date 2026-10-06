"""Local grep configuration for the round-2 trajectory-analysis owner.

Sources: meridianlabs-ai/inspect_scout@0.5.3:
examples/scanner/grep_examples.py:102 (tool-event scanner),
src/inspect_scout/_grep_scanner/_event.py:59 (TOOL prefix),
src/inspect_scout/_grep_scanner/_grep_scanner.py:16 (regex matching).
This config uses Scout's scanner and CLI; it implements no importer or runner.
"""

from inspect_scout import Scanner, Transcript, grep_scanner, scanner


@scanner(events=["tool"])
def delegation() -> Scanner[Transcript]:
    """Count actual Agent/Task tool-event headers, without matching prose."""
    return grep_scanner(
        r"^TOOL \((?:Agent|Task)\):", regex=True, ignore_case=False
    )
