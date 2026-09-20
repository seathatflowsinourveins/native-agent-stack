# Retrieve the maintained catalogs in future sessions

Keep the current clone's Foundation catalog and handbooks in a named QMD index.
Use the installed native QMD from the [session handbook](token-session-handbook.md);
the accepted local version is 2.8.3. The lexical path below requires no downloaded
model, vector embedding or change to either coding client's account.

From the current `native-agent-stack` clone, register these explicitly selected
directories once in a fresh named index:

```sh
CATALOG_DIR="$PWD"
CATALOG_INDEX=native-agent-stack-catalog
qmd --index "$CATALOG_INDEX" collection add "$CATALOG_DIR/catalogs/foundation" --name native-foundation --mask '**/*.md'
qmd --index "$CATALOG_INDEX" collection add "$CATALOG_DIR/docs" --name native-handbooks --mask '**/*.md'
qmd --index "$CATALOG_INDEX" update
qmd --index "$CATALOG_INDEX" search 'Native harness defaults' -c native-handbooks -n 3 --format json
qmd --index "$CATALOG_INDEX" get qmd://native-handbooks/harness-defaults.md
qmd --index "$CATALOG_INDEX" search 'FOUNDATION capability catalog' -c native-foundation -n 3 --format json
qmd --index "$CATALOG_INDEX" get qmd://native-foundation/README.md
```

For an existing index, first inspect the selected collection with
`qmd --index "$CATALOG_INDEX" collection show native-handbooks`. Do not remove
an existing collection merely because it already exists. If its checkout moved,
back up the named YAML configuration and update only that collection's `path`.
The upstream [QMD configuration guide](https://github.com/tobi/qmd#configuring-indexyml)
supports direct edits to collection paths. Preserve masks, contexts, model settings
and unrelated collections, then run `qmd --index "$CATALOG_INDEX" update`.

After a relevant catalog pull or handbook edit, refresh the index before relying
on its contents. Search first, get the selected source and verify its current
revision. Do not preload either complete catalog into an agent session. JSON
capability decisions and receipts remain authoritative structured files; this
Markdown index helps find their guidance and does not turn them into prose claims.

The [recorded native repair](../evidence/receipts/native-catalog-retrieval-20260920.json)
found three adopted collections pointing at an older checkout, corrected their
paths and added the two explicit collections above. Both handbook searches ranked
the intended source first; the returned bodies matched the pinned files exactly
apart from QMD's final display newline. Independent review confirmed the original
three collections changed only paths and that model settings stayed unchanged.
This proves these two current-source retrievals, not arbitrary query recall,
automatic client activation or token savings. The earlier twelve-query benchmark's
four misses remain in its original receipt.
