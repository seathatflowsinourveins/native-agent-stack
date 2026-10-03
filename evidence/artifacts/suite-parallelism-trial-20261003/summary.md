### Suite-parallelism oracle (compare.py)

| OS | Arm | Runs | Eligible runs | Median s | Min s | Max s | Median / S median | Max / S fastest | Controls | Crash | Arm eligible |
|---|---|---|---|---|---|---|---|---|---|---|---|
| macos-15 | S | 0 | 0 | - | - | - | - | - | - | - | no |
| macos-15 | P3 | 0 | 0 | - | - | - | - | - | - | - | no |
| macos-15 | P3F | 0 | 0 | - | - | - | - | - | - | - | no |
| macos-15 | P3C | 0 | 0 | - | - | - | - | - | - | - | no |
| macos-15 | P4 | 0 | 0 | - | - | - | - | - | - | - | no |
| ubuntu-24.04 | S | 3 | 3 | 1659.0 | 1186.0 | 1688.0 | - | - | True | True | yes |
| ubuntu-24.04 | L4 | 3 | 0 | 459.0 | 438.0 | 649.0 | 0.277 | 0.547 | True | True | no |
| ubuntu-24.04 | L4F | 3 | 0 | 692.0 | 539.0 | 710.0 | 0.417 | 0.599 | True | True | no |
| ubuntu-24.04 | L4C | 3 | 0 | 667.0 | 659.0 | 704.0 | 0.402 | 0.594 | True | True | no |

- **macos-15**: no verdict (no run directory); flaky ids in S: 0
- **ubuntu-24.04**: reject (no parallel arm is eligible); flaky ids in S: 0
- id mapping: ok (29 ids, 6 classes rewritten)
- ineligible arm-runs: ubuntu-24.04-L4-r1, ubuntu-24.04-L4-r2, ubuntu-24.04-L4-r3, ubuntu-24.04-L4C-r1, ubuntu-24.04-L4C-r2, ubuntu-24.04-L4C-r3, ubuntu-24.04-L4F-r1, ubuntu-24.04-L4F-r2, ubuntu-24.04-L4F-r3
- failed control runs: none
