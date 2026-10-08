# Local engineering pages: visual plan

The brief is an engineering reading desk: identify the readiness gate, inspect its evidence, find the open gap, and see the next sequenced milestone. The retained approved plan controls palette, source-only content, local navigation, and 320px layouts. This implementation owns presentation and local browser state; the source composer supplies every operational fact.

## Tokens

| Role | Light | Dark |
| --- | --- | --- |
| Canvas | `#f6f8fb` | `#101c2a` |
| Surface | `#ffffff` | `#17283b` |
| Ink | `#183047` | `#e8eef5` |
| Secondary text | `#51677b` | `#b6c6d7` |
| Link and focus | `#205c9b` | `#93c7ff` |
| Measured / pending | `#246d55` / `#996421` | `#86d4b4` / `#f4cc8f` |

Use Ubuntu Sans, Segoe UI, and system sans-serif fallbacks. The same family carries headings and reading text; bold weights distinguish document structure. Tabular numerals align actual dates and counts. Body lines stay near 70 characters. Source code identifiers use the system monospace stack only when the source content needs it.

## Structure

Shared chrome is a narrow blue edge, a plain title, local navigation, and a visibly labelled theme choice. Readiness spends the visual emphasis on a vertical gate rail; evidence uses a wider reading pane. Gaps are a register of ruled rows, with a search box and two labelled filters above the register. Roadmap milestones follow a single visible sequence with a date gutter, title, stated status, and evidence text. Everything is left aligned.

```text
Readiness                 Gap board                    Roadmap
local nav / theme         local nav / theme            local nav / theme
title + source timestamp  title + source timestamp     title + source timestamp
gate rail | evidence      search / group / severity    date | milestone + evidence
gate rail | source table  count                        date | milestone + evidence
gate rail | next boundary  row / source / measurement   date | milestone + evidence
```

At narrow widths the gate rail returns to source order, filters and milestone gutters stack, navigation wraps, and tables retain a labelled horizontal scrolling container. Text and status labels carry meaning independently of color. Controls have visible focus and at least 44px height. No decorative animation, gradients, external assets, font requests, or invented business content are needed.

## Review before implementation

The first plan would normally turn every metric and gap into a card. That would give heterogeneous evidence the same visual importance and waste the small mobile viewport. Use one compact count strip, ruled gap rows, and the gate rail instead. The roadmap has a connected sequence because dates and ordering are real content, rather than decorative numbered markers. Keep outlines only for interactive focus, group boundaries, and source tables. Rounded controls and restrained panel corners express their different functions.

## Sources and limits

- Installed frontend-design guidance: [Anthropic SKILL.md at `683bc88e56f3e09ba94f7055977f3d3aa499f202`](https://github.com/anthropics/skills/blob/683bc88e56f3e09ba94f7055977f3d3aa499f202/skills/frontend-design/SKILL.md), read in full for the two-pass plan, source-specific structure, and critique. Its verified tree `d79e2a5bb4df4a386c2adcdd9ab8709bba28c3f6` matches the installed manifest pin `33375500bcea98d610eb30ce10ac4e59b89c390d`.
- Approved brief: native state root's `research/fullspeed-20261008/g5-stars-gap/local-pages/local-pages-plan.md` (SHA-256 `dd7df012eb9b56c720a5a2c3db3d05adf708b093cc23619b0fa0163b7512dd32`) and retained resume checkpoints.
- Native markup inspected directly: native state root's `coordination/command-center/pages/north-star-readiness.html` (`.wrap`, `.gates/.gate`, `.tl/.row`, `.road/.col`, `.tablewrap`, and status pills). The source API is [`tools/north-star/build_readiness.py` at `af7a4fe65f724e480bf0c79f0795de40a181b37d`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/af7a4fe65f724e480bf0c79f0795de40a181b37d/tools/north-star/build_readiness.py); source builders remain authoritative for status.
- Browser behavior uses native DOM controls, `matchMedia`, `localStorage`, and `hidden`, with storage failure handled locally. Browser screenshots, keyboard/filter checks, and measured contrast are review gates owned by the parent lane; this plan does not claim them complete.
- Native reference behavior checked in current MDN sources on 2026-10-08: [`Window.localStorage`](https://developer.mozilla.org/en-US/docs/Web/API/Window/localStorage) documents `SecurityError` for blocked persistence or invalid origins; [`Window.matchMedia`](https://developer.mozilla.org/en-US/docs/Web/API/Window/matchMedia) documents `matches` and `change` events; the [`hidden` attribute](https://developer.mozilla.org/en-US/docs/Web/HTML/Global_attributes/hidden) documents the CSS display override, so the stylesheet preserves `[hidden]` explicitly.

## Implementation critique

The current operator view uses the read-only `cc-now/1` source at native state
root's `coordination/command-center/pages/cc-now.json`. Its compact headline,
gate count, authored estimate and START-first gate strip precede three desktop
columns for next events, owner actions and workstation readings. Dates put
America/New_York before UTC. Each figure identifies a live sample or dated CC
fallback; the manifest below retains its own gate values and marks superseded
cards. The full input scope moves to a separate sources page. The home page
repeats the same gate strip and links the pages. One short evidence footnote
appears per page.

An actual first desktop measurement placed the summary's bottom at
1004.64px in a 1440×1000 viewport. Smaller checklist row padding and consistent
date sizing retained all actions and placed it at960.55px in both themes.
The browser also checked320px and390px document widths. These are measured
local layout results, separate from CC content approval. An optional pool
disclosure was simplified to plain text after the Vercel review, so the summary
adds no new disclosure state. The original source timestamps and authored
estimate remain visible even when the input merits a custodian correction.

The second pass found that the approved pending foreground `#996421` on the first pale amber fill computed to 4.47:1. Retain that foreground and lighten only the badge fill to `#fff6e8`, which computes to 4.67:1. All other reviewed normal text pairs compute above 4.5:1; the light control border computes to 3.39:1 against its white surface. These are calculations from the stylesheet tokens, not rendered browser measurements.

Long gap titles, milestone titles, source paths, and code identifiers can break at narrow widths instead of forcing page overflow. The system dark fallback is limited to screen media so a script-free preview still prints with the light palette. Gap filtering preserves control focus and uses a polite result-count announcement; an optional reset returns focus to search. No motion or card hover effects were added because they do not explain the evidence.

The CSS expects a native first readiness gate section inside `.readiness-content .wrap`, gap rows inside `#gap-register`, and milestone dates, titles, and states with the retained class names. Source order remains the mobile reading order. Actual desktop/mobile screenshots, keyboard navigation, filter combinations, and persistence/blocked-storage behavior remain parent-lane verification gates.
