# Design tokens

Source: the Pipenzo "Flow look" tokens, `extension/sidepanel/tokens.css` in `jortega0033/clip-to-reel-studio` at commit `a13378ce73e5b27213c9a200fc960ec93afef054` (2026-11-21). The copy is `font_editor/static/tokens.css`, served at `/static/tokens.css` and loaded before `styles.css`.

## Resync

Copy the source file over `font_editor/static/tokens.css`. Do not edit the copy and do nothing else.

## Rule

New UI uses these tokens; no new colour literals in CSS or JavaScript. Canvas code reads a token with `getComputedStyle(document.documentElement).getPropertyValue('--token')` (the `tok()` helper in `app.js`). Colours that are data, such as a colour the user picks, are the only exception and are listed in the pull request.

## Light and dark

Dark is the primary design: black page, alpha layers, one accent. The light block is the matching light theme. The operating system colour scheme (`prefers-color-scheme`) chooses between them; there is no switch in the page. The canvas redraws when the scheme changes.

## Tokens by role

| Role | Tokens |
|---|---|
| Surfaces | `--bg`, `--bg-raised`, `--surface`, `--bg-sunken` |
| Text | `--fg`, `--muted`, `--faint`, `--on-media` |
| Lines | `--border`, `--hairline`, `--control-border`, `--input-border` |
| Accent (one: Pipenzo yellow) | `--primary`, `--primary-press`, `--primary-edge`, `--on-primary`, `--focus` |
| Status | `--success`, `--ok`, `--ok-bg`, `--warn-fg`, `--warn-bg`, `--danger` (the only red), `--danger-bg`, `--info` |
| Dark block | `--ink`, `--on-ink`, `--on-ink-muted`, `--ink-border` |
| Hero | `--hero-bg`, `--on-hero`, `--on-hero-muted`, `--hero-border`, `--hero-chip-border`, `--hero-shadow` |
| Alpha layers | `--glass*`, `--scrim`, `--state-hover`, `--state-selected`, `--btn-secondary`, `--btn-secondary-border`, `--ring-accent`, `--ink-hover` |
| Shadow, gradient | `--shadow-*`, `--grad-*`, `--blur` |
| Type | `--font`, `--font-display`, `--mono` |
| Space, radius | `--space-1` to `--space-7`, `--radius-control`, `--radius-card`, `--radius-media`, `--radius-hero`, `--radius-chip`, `--radius-pill` |
| Motion | `--dur-1` to `--dur-4`, `--ease-out`, `--ease-in-out` |

Yellow only on the primary action and the current selection or step. Red only for danger. Text never sits on a bare alpha layer. The contrast ratios are in the comments of `tokens.css`.
