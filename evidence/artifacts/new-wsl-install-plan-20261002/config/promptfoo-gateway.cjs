// Native Promptfoo config, not an evaluator or provider wrapper.
// promptfoo/promptfoo@34f74d34e140b5e17d23770dfb2340057b1936b8:
// src/util/config/load.ts:383-405; site/docs/providers/openai.md:233-251;
// examples/openai-compatible-gateway/promptfooconfig.yaml:1-24.
// Nonsecret route ownership: adjacent gpt-gateway-topology.json.
const fs = require('node:fs');
const path = require('node:path');
const topology = JSON.parse(fs.readFileSync(
  path.join(__dirname, 'gpt-gateway-topology.json'), 'utf8',
));
const endpoint = topology.gateway?.endpoint;
const gpt = topology.pool_fallback?.model;
const claude = topology.promptfoo?.claude_model;
// Source: https://nodejs.org/api/url.html#urlhostname and #urlport.
// This plan owns exactly the loopback gateway on port 21128.
let url;
try {
  url = new URL(endpoint);
} catch {
  throw new Error('The plan gateway topology must declare its endpoint and distinct GPT/Claude model IDs.');
}
if (typeof endpoint !== 'string' || url.protocol !== 'http:' ||
    url.hostname !== '127.0.0.1' || url.port !== '21128' ||
    url.pathname !== '/v1' || url.username || url.password || url.search || url.hash ||
    [gpt, claude].some(model => typeof model !== 'string' || !model.trim() ||
      ['your-gpt-model-id', 'your-claude-model-id', 'your-model-id'].includes(model) ||
      /[\s\x00-\x1f\x7f]/.test(model)) || gpt === claude) {
  throw new Error('The plan gateway topology must declare its endpoint and distinct GPT/Claude model IDs.');
}

module.exports = {
  description: 'NativeStack gateway GPT and Claude route acceptance',
  sharing: false,
  prompts: ['Answer in one short sentence: {{question}}'],
  providers: [gpt, claude].map((model, index) => ({
    id: `openai:chat:${model}`,
    config: {
      apiBaseUrl: endpoint,
      // The inventory's optional key stays in its environment store. Promptfoo
      // resolves this name natively; no credential value enters this config.
      apiKeyEnvar: 'OMNIROUTE_API_KEY',
      // The plan's gateway is keyless on loopback. An optional stored key is
      // still resolved natively by name when an authenticated host supplies it.
      apiKeyRequired: false,
      useDefaultApiKey: false,
      omitDefaults: true,
      ...(index === 0 && topology.pool_fallback.model_reasoning_effort ?
        {reasoning_effort: topology.pool_fallback.model_reasoning_effort} : {}),
    },
  })),
  tests: [{
    vars: {question: 'What is the capital of France?'},
    assert: [{type: 'contains', value: 'Paris'}],
  }],
};
