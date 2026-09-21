# Automatic local code RAG

SocratiCode watches a deliberately indexed project. Qdrant persists its vectors and code payloads. The local Nemotron embedding service uses query: and passage: prefixes. QMD retrieves Markdown documents separately. File watching runs while the native MCP process is alive, with upstream incremental catch-up on reopening.

Amberquartz persistence marker: 19.
