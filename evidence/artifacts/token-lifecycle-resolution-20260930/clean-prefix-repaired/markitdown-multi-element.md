# Release checklist

Run the **pinned** tools with *scoped* state and read the [upgrade guide](https://example.invalid/guide) first.

## Pinned tools

| Tool | Version | Check |
| --- | --- | --- |
| rtk | 0.50.0 | inline filter tests |
| markitdown | 0.1.8 | structure oracle |
| ast-grep | 0.45.3 | call-site oracle |

### Steps

1. Install into a fresh prefix
2. Run each fixture
3. Keep only sanitized output

* Record every command
  + including failures
* Never read account state

> Evidence is not authority.

```
rtk git log -20
markitdown page.html
```

Tom & Jerry use `--offline` mode.

![Pipeline diagram](diagram.png)