# Primary sources for the WSL persistence drafts

All GitHub source reads used the native command
`gh api repos/<owner>/<repo>/contents/<file>?ref=<full-sha> -H 'Accept: application/vnd.github.raw+json'`.
These are source reads, not boot-application evidence. The numeric ceilings and
swappiness value are the CC's requested policy; the sources establish syntax,
units, placement and behavior.

## Memory and boot

- Installed systemd: `259.5-0ubuntu3.4`. Upstream **systemd/systemd v259.5**,
  `b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a`:
  [controller activation, lines 63–83](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/systemd.resource-control.xml#L63),
  [MemoryAccounting, 309–321](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/systemd.resource-control.xml#L309),
  [MemoryHigh, including infinity at 390](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/systemd.resource-control.xml#L390),
  [MemoryMax and binary suffixes, 406–424](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/systemd.resource-control.xml#L406).
  `MemoryAccounting=yes` enables the controller through ancestors;
  the pinned kernel explains creation of child interface files below.
- Same pin: [unit drop-ins, systemd.unit.xml:203](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/systemd.unit.xml#L203);
  [lexicographic precedence, :233–239](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/systemd.unit.xml#L233);
  [set-property drop-in writer, src/core/unit.c:4735–4740](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/src/core/unit.c#L4735)
  writes priority 50, so the persisted `60-native-stack-memory.conf` sorts
  later. Future policy edits must update the 60- file rather than rely on
  later set-property calls to override it;
  [enablement links, :181–200](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/systemd.unit.xml#L181);
  [slice section, systemd.slice.xml:54](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/systemd.slice.xml#L54);
  [oneshot and RemainAfterExit, systemd.service.xml:209](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/systemd.service.xml#L209);
  [ExecStart, :390](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/systemd.service.xml#L390).
  `systemd.service(5)`, Command lines, specifies `$$` for a literal dollar.
  Shell operations use the [POSIX.1-2024 utilities](https://pubs.opengroup.org/onlinepubs/9799919799/idx/utilities.html)
  `sh`, `test`, `echo` and `read`; the draft's digits-only echo avoids
  option/escape ambiguities.
- Same pin: [sysctl.d boot application and assignment format, sysctl.d.xml:45–82](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/sysctl.d.xml#L45);
  [comments and key/value sections, systemd.syntax.xml:80–90](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/systemd.syntax.xml#L80).
- Installed kernel: `6.18.40.1-microsoft-standard-WSL2`. **microsoft/WSL2-Linux-Kernel**
  tag `linux-msft-wsl-6.18.40.1` →
  `14794180686c2fb6307fbe359c359bec765249f3`:
  [controller interface creation, cgroup-v2.rst:484–503](https://github.com/microsoft/WSL2-Linux-Kernel/blob/14794180686c2fb6307fbe359c359bec765249f3/Documentation/admin-guide/cgroup-v2.rst#L484);
  [memory.max default and OOM behavior, :1381](https://github.com/microsoft/WSL2-Linux-Kernel/blob/14794180686c2fb6307fbe359c359bec765249f3/Documentation/admin-guide/cgroup-v2.rst#L1381);
  [lowering the limit can reclaim/kill, :3386](https://github.com/microsoft/WSL2-Linux-Kernel/blob/14794180686c2fb6307fbe359c359bec765249f3/Documentation/admin-guide/cgroup-v2.rst#L3386);
  [swappiness, vm.rst:959–981](https://github.com/microsoft/WSL2-Linux-Kernel/blob/14794180686c2fb6307fbe359c359bec765249f3/Documentation/admin-guide/sysctl/vm.rst#L959).
  Swappiness is a relative I/O-cost preference, not a swap percentage or cap;
  optimal tuning is workload-dependent.
- Installed WSL: **3.0.1.0**; **microsoft/WSL** tag `3.0.1` →
  `91f161fa240dc355c1a88daabc8aac4273e35ba5`:
  [main.cpp:2280–2281](https://github.com/microsoft/WSL/blob/91f161fa240dc355c1a88daabc8aac4273e35ba5/src/linux/init/main.cpp#L2280)
  creates the distro cgroup and its `non-systemd` child before
  [LaunchInit, :2373](https://github.com/microsoft/WSL/blob/91f161fa240dc355c1a88daabc8aac4273e35ba5/src/linux/init/main.cpp#L2373).
  [Namespace rooting, :3958](https://github.com/microsoft/WSL/blob/91f161fa240dc355c1a88daabc8aac4273e35ba5/src/linux/init/main.cpp#L3958)
  and [init.cpp:2356](https://github.com/microsoft/WSL/blob/91f161fa240dc355c1a88daabc8aac4273e35ba5/src/linux/init/init.cpp#L2356)
  explain the visible `/sys/fs/cgroup/non-systemd` path.
  [util.h:198](https://github.com/microsoft/WSL/blob/91f161fa240dc355c1a88daabc8aac4273e35ba5/src/linux/init/util.h#L198)
  places WSL children in that leaf; [init.cpp:2587](https://github.com/microsoft/WSL/blob/91f161fa240dc355c1a88daabc8aac4273e35ba5/src/linux/init/init.cpp#L2587)
  supplies it for direct payload creation.
  [main.cpp:4298–4330](https://github.com/microsoft/WSL/blob/91f161fa240dc355c1a88daabc8aac4273e35ba5/src/linux/init/main.cpp#L4298)
  removes the subtree at distro exit.
  [System reserve, :105](https://github.com/microsoft/WSL/blob/91f161fa240dc355c1a88daabc8aac4273e35ba5/src/linux/init/main.cpp#L105)
  is 32 MiB; [wsl-user cap, :3908–3909](https://github.com/microsoft/WSL/blob/91f161fa240dc355c1a88daabc8aac4273e35ba5/src/linux/init/main.cpp#L3908)
  is guest `sysinfo` total RAM minus that reserve. The configured VM maximum
  and usable guest MemTotal are different observations.
  [config.cpp:1000](https://github.com/microsoft/WSL/blob/91f161fa240dc355c1a88daabc8aac4273e35ba5/src/linux/init/config.cpp#L1000)
  launches boot.command asynchronously; directory creation alone does not prove
  the memory controller is ready at that point.

## Windows configuration

- Same WSL pin: [stringshared.h:584](https://github.com/microsoft/WSL/blob/91f161fa240dc355c1a88daabc8aac4273e35ba5/src/shared/inc/stringshared.h#L584)
  parses memory suffixes as powers of 1024; `96GB` means 96 GiB,
  while `96GiB` is not an accepted suffix.
  [WslCoreConfig.cpp:309](https://github.com/microsoft/WSL/blob/91f161fa240dc355c1a88daabc8aac4273e35ba5/src/windows/common/WslCoreConfig.cpp#L309)
  clamps memory to physical host memory; [WslCoreVm.cpp:1475](https://github.com/microsoft/WSL/blob/91f161fa240dc355c1a88daabc8aac4273e35ba5/src/windows/service/exe/WslCoreVm.cpp#L1475)
  configures overcommit/deferred commitment. The cap is not an immediate reservation.
  [WslCoreConfig.h:79 and :370](https://github.com/microsoft/WSL/blob/91f161fa240dc355c1a88daabc8aac4273e35ba5/src/windows/common/WslCoreConfig.h#L79)
  accepts dropCache; [util.cpp:3794 and :3947](https://github.com/microsoft/WSL/blob/91f161fa240dc355c1a88daabc8aac4273e35ba5/src/linux/init/util.cpp#L3794)
  implements CPU-idle-gated cache/slab reclaim and compaction, not a hard
  application-memory limit.
  [WslCoreVm.cpp:510](https://github.com/microsoft/WSL/blob/91f161fa240dc355c1a88daabc8aac4273e35ba5/src/windows/service/exe/WslCoreVm.cpp#L510)
  handles the swap VHD path.
- Official **MicrosoftDocs/WSL**, pinned documentation revision
  `7ea1c6f9e25f1c89a05a0e97e5325a02a66ac6cd`:
  [wsl-config.md, .wslconfig / wsl2](https://github.com/MicrosoftDocs/WSL/blob/7ea1c6f9e25f1c89a05a0e97e5325a02a66ac6cd/WSL/wsl-config.md#L227),
  [absolute swapFile path, :240](https://github.com/MicrosoftDocs/WSL/blob/7ea1c6f9e25f1c89a05a0e97e5325a02a66ac6cd/WSL/wsl-config.md#L240),
  and the file's restart / eight-second-rule section. Treat documentation as a
  separate revision from installed-release source.
- Counter meanings: Microsoft's
  [Win32_PerfFormattedData_PerfOS_Memory](https://learn.microsoft.com/en-us/previous-versions/aa394341(v=vs.85))
  and [Win32_PerfFormattedData_PerfProc_Process](https://learn.microsoft.com/en-us/previous-versions/aa394323(v=vs.85)).
  The receipt retains raw bytes and method names. Working-set sums may
  double-count shared pages; private committed memory is not resident memory.

## Time and calendar

- Installed **microsoft/WSL 3.0.1** at
  `91f161fa240dc355c1a88daabc8aac4273e35ba5`:
  [VM-init time agent start, main.cpp:3219–3222](https://github.com/microsoft/WSL/blob/91f161fa240dc355c1a88daabc8aac4273e35ba5/src/linux/init/main.cpp#L3219)
  and [generated configuration/launch, :3698–3710](https://github.com/microsoft/WSL/blob/91f161fa240dc355c1a88daabc8aac4273e35ba5/src/linux/init/main.cpp#L3698)
  start WSL's own chronyd with `refclock PHC /dev/ptp0 poll 3 dpoll -2 offset 0`,
  `makestep 1.0 3` and `rtcsync`. The explicit `::1:323` capture selects its
  PHC0 reference. These offsets establish agreement with the Hyper-V host
  clock, not accuracy against UTC. This is separate from distro configuration;
  no distro PHC refclock confirmation or stable-link edit is needed.
- **MicrosoftDocs/azure-compute-docs**
  `40aaa64a2771acda033ca09289e1e777241f201e`:
  [Linux time-sync.md:102](https://github.com/MicrosoftDocs/azure-compute-docs/blob/40aaa64a2771acda033ca09289e1e777241f201e/articles/virtual-machines/linux/time-sync.md#L102)
  recommends the stable Hyper-V PHC link `/dev/ptp_hyperv`;
  [:127](https://github.com/MicrosoftDocs/azure-compute-docs/blob/40aaa64a2771acda033ca09289e1e777241f201e/articles/virtual-machines/linux/time-sync.md#L127)
  supplies the chrony PHC example. This is Hyper-V/Azure guidance; the
  VM endpoint measurement proves selected PHC0, not the uninspected device link.
  The WSL source above supplies the installed VM-init implementation; the
  Azure example is supporting context rather than a replacement configuration.
- Installed **chrony 4.8**, maintainer mirror **mlichvar/chrony**
  (upstream `gitlab.com/chrony/chrony`),
  `9e8541e3c4c89bfb7a60b404f646fab57c69ce59`:
  [chrony.conf.adoc:573](https://github.com/mlichvar/chrony/blob/9e8541e3c4c89bfb7a60b404f646fab57c69ce59/doc/chrony.conf.adoc#L573)
  documents PHC paths;
  [:634](https://github.com/mlichvar/chrony/blob/9e8541e3c4c89bfb7a60b404f646fab57c69ce59/doc/chrony.conf.adoc#L634)
  documents poll/dpoll and the default refid naming;
  [:1365](https://github.com/mlichvar/chrony/blob/9e8541e3c4c89bfb7a60b404f646fab57c69ce59/doc/chrony.conf.adoc#L1365)
  explains makestep limits and recommends stepping during boot before sensitive programs.
  This PR does not copy the Azure example's unrestricted stepping policy.
  [chronyd.adoc:196–201](https://github.com/mlichvar/chrony/blob/9e8541e3c4c89bfb7a60b404f646fab57c69ce59/doc/chronyd.adoc#L196)
  establishes that `-x` makes no system-clock adjustments and still estimates
  clock error relative to its time sources. The distro monitor is queried at
  `127.0.0.1:3323`; the fresh process receipt retains observed `-x` flags.
  [chronyc.adoc:108–122](https://github.com/mlichvar/chrony/blob/9e8541e3c4c89bfb7a60b404f646fab57c69ce59/doc/chronyc.adoc#L108)
  documents explicit `-h`/`-p` and the default Unix-socket/network fallback.
  The capture queries both daemons by explicit address/port. Distro
  `chronyd --version` does not establish the VM-init daemon's binary version.
  A selected Cloudflare source alone does not prove NTS negotiation; the CC's
  NTS configuration observation is attributed to its read.
- Installed **git/git v2.53.0**, release commit
  `67ad42147a7acc2af6074753ebd03d904476118f`:
  [random minute, builtin/gc.c:2375–2382](https://github.com/git/git/blob/67ad42147a7acc2af6074753ebd03d904476118f/builtin/gc.c#L2375),
  [calendar construction, :3033–3041](https://github.com/git/git/blob/67ad42147a7acc2af6074753ebd03d904476118f/builtin/gc.c#L3033)
  and [scheduler setup, :3235–3247](https://github.com/git/git/blob/67ad42147a7acc2af6074753ebd03d904476118f/builtin/gc.c#L3235)
  show why `git maintenance start` can rewrite all three base timers.
  Check each live base hash against `base_unit_sha256` before applying and
  regenerate the record/drop-ins after a rerun changes them.
- Same systemd 259.5 pin:
  [systemd.time.xml:120 and :254](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/systemd.time.xml#L120)
  defines local/default and explicit zones;
  [systemd.timer.xml:200](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/systemd.timer.xml#L200)
  defines accumulated expressions and reset of calendar **and monotonic** expressions;
  [:86 and :208](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/systemd.timer.xml#L86)
  defines clock-target ordering;
  [:229](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/systemd.timer.xml#L229)
  defines nominal accuracy.
  [test-calendarspec.c:208](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/src/test/test-calendarspec.c#L208)
  covers nonexistent spring times and one fixed ambiguous autumn time.
  The included native enumeration, rather than an assumed DST firing rule,
  determines the proposed expressions' fold behavior.
- Same WSL/docs pins:
  [wsl-config.md:152](https://github.com/MicrosoftDocs/WSL/blob/7ea1c6f9e25f1c89a05a0e97e5325a02a66ac6cd/WSL/wsl-config.md#L152),
  [WslDistributionConfig.h:25 and :58](https://github.com/microsoft/WSL/blob/91f161fa240dc355c1a88daabc8aac4273e35ba5/src/linux/init/WslDistributionConfig.h#L25),
  and [timezone.cpp:49](https://github.com/microsoft/WSL/blob/91f161fa240dc355c1a88daabc8aac4273e35ba5/src/linux/init/timezone.cpp#L49)
  define useWindowsTimezone=true and false skipping the localtime/timezone rewrite.
  The option is independent of chrony synchronization.
- **IANA tzdata 2026b**, **eggert/tz**
  `48c25a1ba86cb602990c0573aba7795417931bb4`:
  [northamerica:188](https://github.com/eggert/tz/blob/48c25a1ba86cb602990c0573aba7795417931bb4/northamerica#L188)
  and [New York zone :341](https://github.com/eggert/tz/blob/48c25a1ba86cb602990c0573aba7795417931bb4/northamerica#L341)
  define the November transition. Installed libc/tz behavior is separately measured.
- UTC server convention, not a requirement: **canonical/subiquity**
  `ccf0196a90b99f01f431927826f65172871a0bda`,
  [autoinstall-reference.rst:1335](https://github.com/canonical/subiquity/blob/ccf0196a90b99f01f431927826f65172871a0bda/doc/reference/autoinstall-reference.rst#L1335)
  gives Etc/UTC as the default-behavior timezone example.

## Selected source byte hashes

| Source at pin above | SHA-256 |
| --- | --- |
| systemd man/systemd.resource-control.xml | 092dea5203a31d93f0022cbd642845bb1c8ae4114ae0ab71d18015d523d3b5e4 |
| systemd man/systemd.service.xml | 99d496aee6b61feb7d1db1949429c561bbe41308227629453ba4e618fb512c56 |
| systemd man/systemd.unit.xml | 6e36f609424ee34df752e1cb38589fdd063924a46702807fc0e0feba77338fe2 |
| systemd man/systemd.slice.xml | 4d9b5ad0eefd3e1c3af356c0fa530bfa8f410ba2cd317a77d026dda3381f6e68 |
| systemd man/sysctl.d.xml | 1b822e8ded938b957934e3a8a1a420c3f0d4e2bb5dd276318ede106f723a993d |
| systemd man/systemd.syntax.xml | cf3ae2757bbbf1b5d91731115cd7a4b4a05b0a83adff42c9ed6591fcc421a466 |
| systemd man/systemd.time.xml | 6ef061a9e90516ebe8324df9db8f73570d80e9d1bc9f83131b4f84e081a79c3b |
| systemd man/systemd.timer.xml | c60ae50a90a2045354e1f34080939bb594e4b790f60385ee5c4c279070483147 |
| WSL src/linux/init/main.cpp | cc905898deadaab394348af30989ca6e77371275eabd365735551d46cf8c9690 |
| WSL src/linux/init/util.h | 5c8d5329e402e545a272c43001bbc279cd075eaad17aa8e9a5894bf3fccba370 |
| WSL src/windows/common/WslCoreConfig.cpp | da428d1aaaccc936c3ad6bbae45c98d34ec4af0361e9f27457dcedc3a15627a9 |
| WSL kernel Documentation/admin-guide/cgroup-v2.rst | e81d1d9be76afdc6ee0a28f109353b1fd0a1f94df0397652988eac0bce4b87cd |
| WSL docs WSL/wsl-config.md | 2f84606529d3486b0b62dadea3afcbcb26cbccdd20ceb6cc0e4470b1520eee74 |
| Azure Linux time-sync.md | f73b8090e09707ec6944dbffee31ab6d2b7bcc8c3b60b9972a75c69bbdd68dbf |
| chrony doc/chrony.conf.adoc | e203e8c18b98069db894e93360dcc15c6475a9f16cb7424612f6e165f5b1d3bb |
| chrony doc/chronyd.adoc | 751ade8be1c264cc87936dc306632be5ba9d2d598018eae6ca42f4485eba06dd |
| chrony doc/chronyc.adoc | d3b0a7dd93fb8bfaf0e0945b49833e955a33f79b5bed35b5861ebb00bc2ff4dc |
| Git builtin/gc.c | 9b33422c7d0c5948a470db5a340992816aedf04dabaf0da6d57e3b004471d775 |
| systemd src/core/unit.c | d4970d32aac859429911a41e7642ca90c1d31f46073b18c9a5f8860cc9f683ee |
