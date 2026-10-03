#!/usr/bin/env python3
"""Rebuild the Modelfile of the measured generation arm S2o (swift-iq3s-s2o) from the Ollama library's published blobs.

The measurement built it as `FROM <the Swift GGUF>` followed by every line of `ollama show --modelfile qwen3.8:27b` except
the lines that begin with `FROM ` or `# FROM ` (line 24 of steps/M13-next.sh in the private measurement folder; its
output is raw/M13-next.txt; both are listed by hash in files.json). The measured file's sha256 is
8911245e6678ee1fac043d31d20de14ea9ed3d8834ccee5beb92e726b769e8f6 (PREREGISTRATION-local-models.md, results of G0).

This program fetches the library model's manifest and its small blobs (config, params, license) from registry.ollama.ai,
checks each against the digest the measurement recorded, renders `ollama show --modelfile` as Ollama v0.35.0
(commit cc4069396f3ad2c370c53eed2e4a42ac13adab84) renders it, and composes the Modelfile:

  server/routes.go:1680-1690   the three header lines and the blank line, then the model's Modelfile
  server/images.go:565-653     the command order: FROM model, FROM projector, TEMPLATE, RENDERER, PARSER, parameters, LICENSE
  parser/parser.go:435-450     how a command prints; parser/parser.go:671-681 when a value is quoted
  template/template.go:94      the default template `{{ .Prompt }}` (the library model has no template layer)
  cmd/cmd.go:1346              `ollama show --modelfile` prints with Println, which adds one final newline

The parameters come from a Go map, so their order differs between calls; the order used here is the one the
measurement's own call printed (raw/M13-next.txt, section 3).

usage:
  reconstruct_s2o_modelfile.py --check   compare with the install plan's Modelfile (exit 1 when it differs)
  reconstruct_s2o_modelfile.py --write   write the install plan's Modelfile
  reconstruct_s2o_modelfile.py --original-from '<the measurement's FROM line>'
                                         also print the sha256 of the measured file rebuilt with that FROM line
Standard library only; needs network access to registry.ollama.ai.
"""
import argparse
import hashlib
import json
import pathlib
import sys
import urllib.request

REGISTRY = "https://registry.ollama.ai/v2/library/qwen3.8"
MANIFEST_DIGEST = "aaee06c39dcf2437cde036998d960e1fc1494b8191be7cc9657d01e509097813"  # qwen3.8:27b, raw/M13-next.txt and run records
MEASURED_SHA256 = "8911245e6678ee1fac043d31d20de14ea9ed3d8834ccee5beb92e726b769e8f6"
PARAMETER_ORDER = ("presence_penalty", "repeat_penalty", "temperature", "top_k", "top_p", "draft_num_predict", "min_p")
PUBLISHED_FROM = "FROM ./Swift-1.5-Qwen3.8-27B-GSQ-RCO-IQ3_S.gguf"
HERE = pathlib.Path(__file__).resolve().parent
TARGET = HERE.parent / "new-wsl-install-plan-20261002" / "models" / "swift-iq3s-s2o.Modelfile"


def fetch(url, accept=None):
    request = urllib.request.Request(url, headers={"Accept": accept} if accept else {})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def verified(data, digest, what):
    got = hashlib.sha256(data).hexdigest()
    if got != digest:
        raise SystemExit(f"{what}: sha256 {got} is not the recorded {digest}")
    return data


def quote(value):
    """parser/parser.go:671-681."""
    if "\n" in value or value.startswith(" ") or value.endswith(" "):
        return '"""' + value + '"""' if '"' in value else '"' + value + '"'
    return value


def go_value(value):
    """fmt.Sprintf("%v", v) of a JSON number decoded into any (a float64), for the values this model carries."""
    if isinstance(value, float) and value.is_integer() or isinstance(value, int):
        return str(int(value))
    return repr(float(value))


def body():
    manifest = verified(fetch(f"{REGISTRY}/manifests/27b", "application/vnd.docker.distribution.manifest.v2+json"),
                        MANIFEST_DIGEST, "manifest qwen3.8:27b")
    doc = json.loads(manifest)
    layers = {layer["mediaType"]: layer["digest"].split(":", 1)[1] for layer in doc["layers"]}
    if "application/vnd.ollama.image.template" in layers:
        raise SystemExit("the library model now has a template layer; this rendering assumes the default template")
    config = json.loads(verified(fetch(f"{REGISTRY}/blobs/sha256:{doc['config']['digest'].split(':', 1)[1]}"),
                                 doc["config"]["digest"].split(":", 1)[1], "config"))
    params = json.loads(verified(fetch(f"{REGISTRY}/blobs/sha256:{layers['application/vnd.ollama.image.params']}"),
                                 layers["application/vnd.ollama.image.params"], "params"))
    license_text = verified(fetch(f"{REGISTRY}/blobs/sha256:{layers['application/vnd.ollama.image.license']}"),
                            layers["application/vnd.ollama.image.license"], "license").decode("utf-8")
    if sorted(params) != sorted(PARAMETER_ORDER):
        raise SystemExit(f"the library model's parameters changed: {sorted(params)}")
    # The two FROM lines (model and projector) and the `# FROM` comment are dropped by the composition, so their
    # paths do not matter; they are kept here only so that the rendered text is the one the measurement filtered.
    commands = ["FROM <model blob>", "FROM <projector blob>", "TEMPLATE " + quote("{{ .Prompt }}"),
                "RENDERER " + quote(config["renderer"]), "PARSER " + quote(config["parser"])]
    commands += [f"PARAMETER {name} {quote(go_value(params[name]))}" for name in PARAMETER_ORDER]
    commands += ["LICENSE " + quote(license_text)]
    shown = ('# Modelfile generated by "ollama show"\n# To build a new Modelfile based on this, replace FROM with:\n'
             "# FROM qwen3.8:27b\n\n" + "".join(command + "\n" for command in commands)) + "\n"
    if shown.count("\n") != 221:
        raise SystemExit(f"the rendered library Modelfile has {shown.count(chr(10))} lines, the record says 221")
    return "".join(line for line in shown.splitlines(keepends=True)
                   if not line.startswith("FROM ") and not line.startswith("# FROM "))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    parser.add_argument("--original-from", help="the measurement's FROM line, to rebuild the measured file and hash it")
    args = parser.parse_args()
    rest = body()
    published = PUBLISHED_FROM + "\n" + rest
    print(f"published Modelfile: {published.count(chr(10))} lines, sha256 {hashlib.sha256(published.encode()).hexdigest()}")
    if args.original_from is not None:
        original = args.original_from.rstrip("\n") + "\n" + rest
        digest = hashlib.sha256(original.encode()).hexdigest()
        print(f"measured Modelfile rebuilt with the given FROM line: sha256 {digest} "
              f"({'equal to' if digest == MEASURED_SHA256 else 'NOT'} the recorded {MEASURED_SHA256})")
        if digest != MEASURED_SHA256:
            return 1
    if args.write:
        TARGET.parent.mkdir(parents=True, exist_ok=True)
        TARGET.write_text(published, encoding="utf-8")
        print(f"wrote {TARGET.relative_to(HERE.parents[2]).as_posix()}")
    elif args.check:
        current = TARGET.read_text(encoding="utf-8") if TARGET.exists() else None
        if current != published:
            print("the install plan's Modelfile differs from the reconstruction")
            return 1
        print("the install plan's Modelfile equals the reconstruction")
    return 0


if __name__ == "__main__":
    sys.exit(main())
