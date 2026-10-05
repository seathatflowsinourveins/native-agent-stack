// CL7: one Codex SDK (@openai/codex-sdk 0.160.0) thread, written from the SDK README's runStreamed() example.
// Run by launcher.py under the CL3 timeout. Every streamed event is written to stdout as one JSON line, the same event
// shapes as `codex exec --json` (thread.started, item.*, turn.*), so one grader reads CL3 and CL7.
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
};
const codex = new sdk.Codex({
  codexPathOverride: arg("codex-path"),
  env,
  configOverrides: ['profile="omniroute"', 'service_tier="default"', `otel.environment="${trialId}"`],
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
