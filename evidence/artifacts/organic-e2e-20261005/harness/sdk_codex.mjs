// CL7: one Codex SDK (@openai/codex-sdk 0.160.0) thread, written from the SDK README's runStreamed() example.
// Run by launcher.py under the CL3 timeout. Every streamed event is written to stdout as one JSON line, the same event
// shapes as `codex exec --json` (thread.started, item.*, turn.*), so one grader reads CL3 and CL7.
// The omniroute profile comes in as the SDK's config object (--profile-config, written at stage 1 by
// prepare.codex_profile_layer): the SDK builds `codex exec` without --profile, and codex 0.160.0 refuses
// `profile = "omniroute"` through --config, so the profile file's keys go in as --config overrides instead.
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { join } from "node:path";

function arg(name) {
  const index = process.argv.indexOf(`--${name}`);
  if (index < 0 || index + 1 >= process.argv.length) throw new Error(`missing --${name}`);
  return process.argv[index + 1];
}

const trialId = arg("trial-id");
const sdk = await import(pathToFileURL(join(arg("sdk-dir"), "dist", "index.js")).href);
const env = {
  PATH: process.env.PATH ?? "",
  HOME: process.env.HOME ?? "",
  LANG: process.env.LANG ?? "C.UTF-8",
  CODEX_HOME: arg("codex-home"),
  OMNIROUTE_API_KEY: "local-loopback",
  OTEL_RESOURCE_ATTRIBUTES: arg("otel"),
  // §8.3: every trial runs with GH_CONFIG_DIR (the clone's config also sets it for the shell tool and MCP servers).
  GH_CONFIG_DIR: arg("gh-config-dir"),
};
const codex = new sdk.Codex({
  codexPathOverride: arg("codex-path"),
  env,
  config: JSON.parse(readFileSync(arg("profile-config"), "utf8")),
  configOverrides: ['service_tier="default"', `otel.environment="${trialId}"`],
});
const thread = codex.startThread({
  workingDirectory: arg("cwd"),
  skipGitRepoCheck: true,
  model: "gpt-6.1-sol",
  modelReasoningEffort: arg("effort"),
  sandboxMode: arg("sandbox"),
  approvalPolicy: "never",
  networkAccessEnabled: false,
});
const { events } = await thread.runStreamed(readFileSync(arg("prompt-file"), "utf8"));
for await (const event of events) {
  process.stdout.write(JSON.stringify(event) + "\n");
}
