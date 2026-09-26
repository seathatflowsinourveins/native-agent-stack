// local_integration client (self-written; not an upstream test) for socraticode's documented launch.
// socraticode's README configures MCP clients to run the package as a stdio server
// (`npx -y --prefer-online socraticode@latest`, or `node /absolute/path/to/socraticode/dist/index.js`;
// the installed `socraticode` bin is that dist/index.js). This starts SERVER_COMMAND that way through the MCP
// TypeScript SDK client in socraticode's own dependency tree, prints the server's identity and tool
// names, and compares the names with the `codebase_*` rows of the installed README's tool tables.
// Exit 0 only when initialize and tools/list both succeed and list at least one tool.
//   usage: node mcp_list_tools.mjs SOCRATICODE_PACKAGE_DIR SERVER_COMMAND [ARG...]
import fs from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";

const [base, command, ...args] = process.argv.slice(2);
const req = createRequire(path.join(base, "package.json"));
const clientEntry = req.resolve("@modelcontextprotocol/sdk/client/index.js");
const { Client } = req(clientEntry);
const { StdioClientTransport } = req("@modelcontextprotocol/sdk/client/stdio.js");
let sdkRoot = path.dirname(clientEntry);
for (;;) {
  const manifest = path.join(sdkRoot, "package.json");
  if (fs.existsSync(manifest) && JSON.parse(fs.readFileSync(manifest, "utf-8")).name === "@modelcontextprotocol/sdk") break;
  if (path.dirname(sdkRoot) === sdkRoot) throw new Error(`no @modelcontextprotocol/sdk package.json above ${clientEntry}`);
  sdkRoot = path.dirname(sdkRoot);
}
const sdkVersion = JSON.parse(fs.readFileSync(path.join(sdkRoot, "package.json"), "utf-8")).version;
console.log(`client: @modelcontextprotocol/sdk ${sdkVersion} from ${path.relative(base, sdkRoot)}`);
console.log(`server command: ${[command, ...args].join(" ")}`);

const transport = new StdioClientTransport({ command, args, env: { ...process.env }, stderr: "pipe" });
let serverStderr = "";
transport.stderr?.on("data", (chunk) => { serverStderr += String(chunk); });
const client = new Client({ name: "bootstrap-integrity-mcp-list-tools", version: "1.0.0" });
let ok = false;
try {
  await client.connect(transport);
  const server = client.getServerVersion();
  console.log(`initialize: server ${server?.name} ${server?.version}`);
  const { tools } = await client.listTools();
  const names = tools.map((tool) => tool.name).sort();
  console.log(`tools/list: ${names.length} tool(s): ${names.join(" ")}`);
  const readme = fs.readFileSync(path.join(base, "README.md"), "utf-8");
  const documented = [...new Set([...readme.matchAll(/^\| `(codebase_[a-z_]+)` \|/gm)].map((match) => match[1]))].sort();
  console.log(`README tool tables: ${documented.length} codebase_* tool(s)`);
  console.log(`listed, not in those tables: ${names.filter((name) => !documented.includes(name)).join(" ") || "none"}`);
  console.log(`in those tables, not listed: ${documented.filter((name) => !names.includes(name)).join(" ") || "none"}`);
  ok = names.length > 0;
} catch (error) {
  console.log(`FAILED: ${String(error?.message ?? error).split("\n")[0]}`);
} finally {
  await client.close().catch(() => {});
}
const lines = serverStderr.split("\n").filter((line) => line.trim());
console.log(`server stderr: ${lines.length} line(s)`);
for (const line of lines.slice(0, 20)) console.log(`  ${line}`);
process.exitCode = ok ? 0 : 1;
