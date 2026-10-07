# MinerU local source through a user service

Status: proposed integration for the command center's host-change window. Creating this template does not install or qualify a running service. The completed A23/D09 process-local parse remains a separate dated observation.

The user unit runs the installed MinerU 4.0.10 DocLib module in the foreground and sets `MINERU_MODEL_SOURCE=local` at startup. Native clients use that service; they do not start, stop or restart another DocLib themselves. This provides a durable launch carrier without changing the installed skill, either client, the keyed configuration file, or #723's install-plan inputs. The owner's existing first-install prefix remains in place until that owner changes it.

The maintainer documents `mineru server start`, which launches `sys.executable -m mineru.doclib.app`. The shipped module also has the foreground server loop used here. This unit is our integration of that entry, not a verified upstream systemd recipe. Sources: [MinerU@c221cc41 README.md:462](https://github.com/opendatalab/MinerU/blob/c221cc41bc911ad0df3eaeda97acf6a1bfe9bf93/README.md#L462), [server.py:242](https://github.com/opendatalab/MinerU/blob/c221cc41bc911ad0df3eaeda97acf6a1bfe9bf93/mineru/cli/commands/server.py#L242), and [app.py:443](https://github.com/opendatalab/MinerU/blob/c221cc41bc911ad0df3eaeda97acf6a1bfe9bf93/mineru/doclib/app.py#L443).

The native environment override is resolved when the process imports its configuration. DocLib passes its environment to its managed parser. Changing a later CLI's environment does not change an existing service. Sources: [config.py:156](https://github.com/opendatalab/MinerU/blob/c221cc41bc911ad0df3eaeda97acf6a1bfe9bf93/mineru/config.py#L156), [config.py:236](https://github.com/opendatalab/MinerU/blob/c221cc41bc911ad0df3eaeda97acf6a1bfe9bf93/mineru/config.py#L236), and [parse_server_health.py:205](https://github.com/opendatalab/MinerU/blob/c221cc41bc911ad0df3eaeda97acf6a1bfe9bf93/mineru/doclib/background/parse_server_health.py#L205).

## Command center apply and read-back

Only the CC executes this section in its announced host-change window. Keep every exit code and returned read-back in a new receipt; follow [owned lifecycle](../adoption/lifecycle.md) and the [evidence policy](../docs/acceptance-evidence-policy.md).

1. Verify `mineru version --json` reports the selected version. Run `uv tool dir --offline` and confirm the existing environment's interpreter is executable. The template assumes uv's default Linux root, `%h/.local/share/uv/tools/mineru/bin/python`. A different `UV_TOOL_DIR` or `XDG_DATA_HOME` requires rendering that actual interpreter path before installation, rather than installing another tool. See [uv's tools storage](https://docs.astral.sh/uv/reference/storage/#tools) and [persistent isolated tool environments](https://docs.astral.sh/uv/concepts/tools/#tool-environments), read 2026-10-07.
2. Check `systemctl --user show stack-alert@mineru.service.service --property=LoadState` reports a loaded handler. The required `OnFailure=stack-alert@%n.service` expands to that name. The handler is CC-owned; this recipe supplies no replacement and claims no installed handler. Resolve the CPU-guard condition below before a parse that requires CPU-only operation.
3. Stop any existing standalone DocLib through its native command, and confirm its status before starting the unit. Install the template, reload the user manager, verify the unit, then enable and start it:

   ```sh
   mineru server stop
   mineru server status --json
   install -Dm0644 adoption/templates/systemd/mineru.service "$HOME/.config/systemd/user/mineru.service"
   systemctl --user daemon-reload
   systemd-analyze --user verify "$HOME/.config/systemd/user/mineru.service"
   systemctl --user enable --now mineru.service
   ```

4. Read only bounded unit metadata, then the native service status:

   ```sh
   systemctl --user show mineru.service --property=Id,LoadState,ActiveState,SubState,MainPID,FragmentPath,ExecMainStatus,Result,NRestarts,OnFailure
   mineru server status --json
   ```

   The reviewed source shows startup inheritance; these status fields do not provide a native running-server `model.source` getter. Record the installed template identity, the fresh service start and its status as configuration and integration evidence. Do not print complete unit/process environments, inspect `/proc` environments, or read/copy the keyed YAML. A same-environment `mineru-kit models show` describes that diagnostic process, not the running service's source.
5. From a fresh native-client shell with no manual source export, the CC parses the installed public `demo1.pdf` once:

   ```sh
   nice -n 19 ionice -c3 mineru parse "$HOME/.local/share/new-wsl-native-stack/tools/mineru/demo1.pdf" --tier standard --pages 1 --wait 600 --json
   ```

   Preserve the result, cache status and page/block locators. This named smoke is integration evidence, not organic use or an unchanged upstream harness. A23's earlier single parse is not repeated by this lane.

For later lifecycle operations, the CC uses `systemctl --user stop|start|restart mineru.service`. The unit owns the foreground DocLib and its children. Automatic failure restart uses a five-second delay and at most three starts within 60 seconds; unrecovered failure reaches the CC's alert handler. `Type=exec` proves execution of the binary, not parser readiness, so native status remains necessary. Sources: [systemd@v260 service semantics](https://github.com/systemd/systemd/blob/v260/man/systemd.service.xml#L158), [unit failure and start-limit semantics](https://github.com/systemd/systemd/blob/v260/man/systemd.unit.xml), and [control-group stop semantics](https://github.com/systemd/systemd/blob/v260/man/systemd.kill.xml#L56), checked against this host's systemd 259 manual on 2026-10-07.

## CPU-guard condition remains open

Do not claim that `LLAMA_ARG_N_GPU_LAYERS=0` guards the embedded parser. The installed `mineru_llama_cpp/engine.py:52,107-108` defaults `n_gpu_layers` to 99 and passes the argument into its native core. [MinerU@c221cc41 runtime.py:175](https://github.com/opendatalab/MinerU/blob/c221cc41bc911ad0df3eaeda97acf6a1bfe9bf93/mineru/model/vlm/runtime.py#L175) passes explicit engine kwargs. The separate [llama_cpp_server.py:263](https://github.com/opendatalab/MinerU/blob/c221cc41bc911ad0df3eaeda97acf6a1bfe9bf93/mineru/kit/vlm_server/llama_cpp_server.py#L263) supports that environment variable for its external llama-server wrapper; this is a different entry from the embedded engine.

Those source observations do not establish an effective environment guard for the embedded route. The unit therefore sets source only. The CC must settle and qualify an upstream-supported CPU guard before claiming CPU-only acceptance; no new wrapper, backend change or ineffective environment setting is supplied here.
