// local_integration probe (self-written; not an upstream test), run by check.py with the pinned node.
// Do the 18 socraticode dependencies whose install scripts npm skipped still work natively?
//   usage: node native_probe.cjs SOCRATICODE_PACKAGE_DIR SCRATCH_DIR
// 1. The 16 @ast-grep/lang-* grammars are registered in one registerDynamicLanguage batch with
//    @ast-grep/napi, as socraticode's own ensureDynamicLanguages does, and each then parses a snippet.
// 2. tree-sitter-gdscript is checked with socraticode's own dist/services/gdscript-preflight.cjs
//    (native addon require, language export, ast-grep registration and parse).
// 3. @parcel/watcher subscribes to SCRATCH_DIR and unsubscribes through its native binding.
// 4. Control: a copy of @ast-grep/lang-bash whose parser.so is cut to 64 bytes must be refused, so
//    step 1 is a real load and not only a path lookup.
"use strict";
const { createRequire } = require("node:module");
const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const base = process.argv[2];
const scratch = process.argv[3];
const req = createRequire(path.join(base, "package.json"));
const { registerDynamicLanguage, parse } = req("@ast-grep/napi");
const snippets = {
  bash: "echo hi\n", c: "int main(void) { return 0; }\n", cpp: "int main() { return 0; }\n",
  csharp: "class A {}\n", dart: "void main() {}\n", elixir: "x = 1\n", go: "package main\n",
  java: "class A {}\n", kotlin: "fun main() {}\n", lua: "local x = 1\n", php: "<?php echo 1;\n",
  python: "x = 1\n", ruby: "x = 1\n", rust: "fn main() {}\n", scala: "object A\n", swift: "let x = 1\n",
};
let failures = 0;
const report = (ok, text) => { failures += ok ? 0 : 1; console.log(`${ok ? "ok" : "FAILED"} ${text}`); };

const grammars = {};
for (const name of Object.keys(snippets)) grammars[name] = req(`@ast-grep/lang-${name}`);
registerDynamicLanguage(grammars);
for (const [name, code] of Object.entries(snippets)) {
  try {
    const root = parse(name, code).root();
    const errors = root.findAll({ rule: { kind: "ERROR" } }).length;
    report(root.children().length > 0 && errors === 0,
      `@ast-grep/lang-${name}: parsed ${JSON.stringify(code.trim())} -> ${root.kind()} ` +
      `(${root.children().length} child node(s), ${errors} ERROR node(s)) from ` +
      path.relative(base, grammars[name].libraryPath));
  } catch (error) {
    report(false, `@ast-grep/lang-${name}: ${String(error.message).split("\n")[0]}`);
  }
}

const preflight = path.join(base, "dist/services/gdscript-preflight.cjs");
try {
  const out = execFileSync(process.execPath, [preflight, req.resolve("tree-sitter-gdscript/package.json")],
    { encoding: "utf-8", timeout: 30000 }).trim();
  const match = out.match(/^PREFLIGHT: OK (.+)$/m);
  report(Boolean(match), `tree-sitter-gdscript: socraticode's gdscript-preflight.cjs printed ` +
    `${JSON.stringify(match ? `PREFLIGHT: OK ${path.relative(base, match[1])}` : out)}`);
} catch (error) {
  report(false, `tree-sitter-gdscript: ${String(error.stdout || error.message).split("\n")[0]}`);
}

(async () => {
  try {
    const watcher = req("@parcel/watcher");
    const subscription = await watcher.subscribe(scratch, () => {});
    await subscription.unsubscribe();
    report(true, "@parcel/watcher: subscribe and unsubscribe through its native binding");
  } catch (error) {
    report(false, `@parcel/watcher: ${String(error.message).split("\n")[0]}`);
  }
  // Control: a truncated parser.so in a copy of lang-bash. @ast-grep/napi aborts the whole process
  // (a Rust panic on the failed dlopen) instead of throwing, so the control runs in a child process.
  const copy = path.join(scratch, "lang-bash-truncated");
  fs.cpSync(path.dirname(req.resolve("@ast-grep/lang-bash/package.json")), copy, { recursive: true });
  const parser = path.join(copy, "prebuilds/prebuild-Linux-X64/parser.so");
  fs.truncateSync(parser, 64);
  const control = `const { registerDynamicLanguage, parse } = require(${JSON.stringify(req.resolve("@ast-grep/napi"))});
    registerDynamicLanguage({ bash: { libraryPath: process.argv[1], languageSymbol: "tree_sitter_bash", extensions: ["sh"] } });
    parse("bash", "echo hi\\n");
    console.log("accepted");`;
  try {
    execFileSync(process.execPath, ["-e", control, parser], { encoding: "utf-8", timeout: 30000, stdio: ["ignore", "pipe", "pipe"] });
    report(false, "control: a 64-byte parser.so was accepted");
  } catch (error) {
    const stderr = String(error.stderr || "");
    const line = stderr.split("\n").find((text) => text.includes("DlOpen")) || stderr.split("\n")[0];
    report(/DlOpen/.test(stderr),
      `control: a 64-byte parser.so is refused (child ${error.signal || `exit ${error.status}`}): ${line.trim()}`);
  }
  console.log(`${failures} failure(s)`);
  process.exitCode = failures ? 1 : 0;
})();
